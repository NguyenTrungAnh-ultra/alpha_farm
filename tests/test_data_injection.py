"""Engines take their data from the caller: sub-window search, keyed HMM caches, calendar-correct annualisation."""
import os

import joblib
import numpy as np
import pandas as pd
import pytest

pytest.importorskip('hmmlearn')

import core_engine.BacktestEngine as backtest_module
import strategy_workflows.HMMValidation as hmm_module
from core_engine.BacktestEngine import load_data
from core_engine.CalculateMetrics import compute_metrics
from strategy_workflows.HMMValidation import (
    KEYED_CACHE_SUBDIR,
    calculate_buy_hold_metrics,
    fit_hmm_model,
    generate_synthetic_ohlcv,
    precompute_hmm_synthetic_data,
)
from strategy_workflows.MCTSEngine import MCTSEngine
from strategy_workflows.SemanticCompiler import SemanticCompiler
from utilities.AppConfig import HMM_COMPONENTS

WINDOW_START, WINDOW_END = '2022-01-01', '2022-06-30'


def _forbid_load_data(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("load_data was called although the caller supplied the data")
    monkeypatch.setattr('strategy_workflows.MCTSEngine.load_data', boom)
    monkeypatch.setattr(backtest_module, 'load_data', boom)
    monkeypatch.setattr(hmm_module, 'load_data', boom, raising=False)


@pytest.fixture(scope="module")
def full_60m():
    return load_data('60m')


@pytest.fixture(scope="module")
def full_1m():
    return load_data('1m')


@pytest.fixture(scope="module")
def full_30m():
    return load_data('30m')


@pytest.fixture(scope="module")
def full_60m_alias(full_60m):
    return full_60m


# --- (a) MCTS searches only the injected window -------------------------------------------

def test_mcts_searches_only_the_injected_window(full_60m, monkeypatch):
    window = full_60m[WINDOW_START:WINDOW_END].copy()
    assert 0 < len(window) < len(full_60m)
    _forbid_load_data(monkeypatch)

    engine = MCTSEngine(timeframe='60m', seed=3, data=window)
    seen = []
    original_run = engine.backtest_engine.run

    def spy(strategy, df):
        seen.append((df.index.min(), df.index.max(), len(df)))
        return original_run(strategy, df)

    engine.backtest_engine.run = spy
    engine.run_search_from_blueprint(SemanticCompiler().compile_blueprint("sub(ts_mean(?), ts_mean(?))"), n_iterations=60)

    assert seen, "no backtest was evaluated"
    lo, hi = pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END) + pd.Timedelta(days=1)
    assert all(lo <= first and last < hi and n == len(window) for first, last, n in seen)
    assert engine.data.pv_close.index.equals(window.index)


# --- (b) HMM cache is keyed by the data it was fitted on ----------------------------------

def test_hmm_cache_keeps_one_entry_per_data_window(dummy_ohlcv_data, temp_hmm_cache, monkeypatch):
    monkeypatch.setattr(hmm_module, 'MC_CACHE_DIR', temp_hmm_cache)
    _forbid_load_data(monkeypatch)
    window_a, window_b = dummy_ohlcv_data.iloc[:600], dummy_ohlcv_data.iloc[300:900]

    builds = []
    real_build = hmm_module._build_paths
    monkeypatch.setattr(hmm_module, '_build_paths', lambda df, n: builds.append(df.index[0]) or real_build(df, n))

    result_a = precompute_hmm_synthetic_data({'15m': window_a}, n_paths=2)
    result_b = precompute_hmm_synthetic_data({'15m': window_b}, n_paths=2)

    cache_dir = os.path.join(temp_hmm_cache, KEYED_CACHE_SUBDIR)
    assert len(os.listdir(cache_dir)) == 2
    assert builds == [window_a.index[0], window_b.index[0]]
    assert not result_a['15m']['normal'][0].index.equals(result_b['15m']['normal'][0].index)

    again_a = precompute_hmm_synthetic_data({'15m': window_a}, n_paths=2)
    assert builds == [window_a.index[0], window_b.index[0]], "same data must be served from its cache"
    pd.testing.assert_frame_equal(again_a['15m']['normal'][0], result_a['15m']['normal'][0])

    precompute_hmm_synthetic_data({'15m': window_a}, n_paths=2, force_retrain=True)
    assert len(builds) == 3


def test_changed_close_value_is_a_different_cache_entry(dummy_ohlcv_data, temp_hmm_cache, monkeypatch):
    monkeypatch.setattr(hmm_module, 'MC_CACHE_DIR', temp_hmm_cache)
    tweaked = dummy_ohlcv_data.copy()
    tweaked.iloc[500, tweaked.columns.get_loc('Close')] *= 1.001

    precompute_hmm_synthetic_data({'15m': dummy_ohlcv_data}, n_paths=1)
    precompute_hmm_synthetic_data({'15m': tweaked}, n_paths=1)

    assert len(os.listdir(os.path.join(temp_hmm_cache, KEYED_CACHE_SUBDIR))) == 2


def test_legacy_cache_without_metadata_is_not_reused_nor_deleted(dummy_ohlcv_data, temp_hmm_cache, monkeypatch, capsys):
    monkeypatch.setattr(hmm_module, 'MC_CACHE_DIR', temp_hmm_cache)
    legacy = os.path.join(temp_hmm_cache, hmm_module.LEGACY_CACHE_FILENAME)
    joblib.dump({'15m': {'normal': ['old'], 'stressed': ['old']}}, legacy)

    result = precompute_hmm_synthetic_data({'15m': dummy_ohlcv_data}, n_paths=1)

    assert result == {}
    assert os.path.exists(legacy)
    assert '--retrain-hmm' in capsys.readouterr().out

    forced = precompute_hmm_synthetic_data({'15m': dummy_ohlcv_data}, n_paths=1, force_retrain=True)
    assert len(forced['15m']['normal']) == 1
    assert os.path.exists(legacy)


# --- (c) annualisation is calendar-correct for every timeframe ----------------------------

def _calendar_cagr(df):
    years = (df.index[-1] - df.index[0]).days / 365.25
    return (df['Close'].iloc[-1] / df['Close'].iloc[0]) ** (1 / years) - 1


@pytest.mark.parametrize("tf_fixture", ["full_1m", "full_30m", "full_60m_alias"])
def test_buy_hold_cagr_matches_compute_metrics_and_calendar(tf_fixture, request):
    df = request.getfixturevalue(tf_fixture)
    sharpe, cagr, _ = calculate_buy_hold_metrics(df)

    equity = df['Close'] / df['Close'].iloc[0]
    result = hmm_module.BacktestResult(
        equity_curve=equity, positions=pd.Series(1.0, index=df.index), trades=[],
        initial_capital=1.0, final_equity=float(equity.iloc[-1]), total_fees=0.0, total_trades=0)
    assert cagr == pytest.approx(compute_metrics(result)['cagr_pct'] / 100.0, abs=1e-9)
    assert cagr == pytest.approx(_calendar_cagr(df), abs=0.002)
    assert cagr == pytest.approx(0.089, abs=0.003)


def test_buy_hold_cagr_agrees_across_timeframes(full_1m, full_30m, full_60m):
    cagrs = [calculate_buy_hold_metrics(d)[1] for d in (full_1m, full_30m, full_60m)]
    assert max(cagrs) - min(cagrs) < 0.002, "files with missing session days must not change the CAGR"


# --- (d) synthetic paths carry the source's trading calendar -------------------------------

def test_synthetic_path_uses_the_sources_trading_days(full_60m):
    source = full_60m[WINDOW_START:WINDOW_END]
    _, df_clean, _ = fit_hmm_model(source, n_components=HMM_COMPONENTS)
    path = generate_synthetic_ohlcv(df_clean, np.full((HMM_COMPONENTS, HMM_COMPONENTS), 1.0 / HMM_COMPONENTS),
                                    len(df_clean), 20, random_seed=1)

    assert path.index.equals(df_clean.index[:len(path)])
    path_days = path.index.normalize().nunique()
    source_days = df_clean.index.normalize().nunique()
    assert path_days >= source_days - 1
    assert 100 <= path_days <= 140, "6 months of VN30F sessions is roughly 125 trading days"

    cagr = calculate_buy_hold_metrics(path)[1]
    years = (path.index[-1] - path.index[0]).total_seconds() / (365.25 * 86400)
    expected = (path['Close'].iloc[-1] / path['Close'].iloc[0]) ** (1.0 / years) - 1
    assert cagr == pytest.approx(expected, rel=1e-6, abs=1e-6)


# --- (e) the per-timeframe worker uses only the frame it is given --------------------------

def test_process_timeframe_uses_only_the_injected_frame(full_60m, tmp_path, monkeypatch):
    import json
    import strategy_workflows.RunMCTS as run_module
    from core_engine.BacktestEngine import AlphaBacktestEngine
    from strategy_workflows.MCTSEngine import MCTSEngine as Engine

    window = full_60m[WINDOW_START:WINDOW_END].copy()
    ideas = tmp_path / "results" / "ideas"
    ideas.mkdir(parents=True)
    (ideas / "idea_60m.json").write_text(json.dumps({"name": "idea", "macro_blueprint": "sub(ts_mean(?), ts_mean(?))"}))

    monkeypatch.setattr(run_module, 'PROJECT_ROOT', str(tmp_path))
    _forbid_load_data(monkeypatch)
    monkeypatch.setattr(run_module, 'load_data', lambda *a, **k: (_ for _ in ()).throw(AssertionError("load_data called")))
    # A fixed candidate guarantees the replay backtest runs regardless of what the short search finds.
    monkeypatch.setattr(Engine, 'get_best_candidates', lambda self: [{
        'expr': 'ts_mean(close, 5)', 'direction': 1.0, 'template': 'NORMALIZED', 'window': 20,
        'z_score': 1.0, 'reward': 1.0, 'metrics': {}}])

    seen = []
    original_run = AlphaBacktestEngine.run

    def spy(self, strategy, df):
        seen.append((df.index.min(), df.index.max(), len(df)))
        return original_run(self, strategy, df)

    monkeypatch.setattr(AlphaBacktestEngine, 'run', spy)

    tf, generated, rejected, successful = run_module.process_timeframe('60m', window, 20, {}, seed=1)

    assert len(successful) == 1
    lo, hi = pd.Timestamp(WINDOW_START), pd.Timestamp(WINDOW_END) + pd.Timedelta(days=1)
    assert seen and all(lo <= first and last < hi and n == len(window) for first, last, n in seen)
    assert successful[0]['equity_curve'].index.equals(window.index)
