"""Reward modes: "gated" / "soft" stay as they were, "sharpe" scores Sharpe and the IC of the traded signal."""
import json

import numpy as np
import pandas as pd
import pytest

from core_engine.AlphaPrimitives import ts_zscore
from strategy_workflows.MCTSEngine import MCTSEngine, describe_candidate
from strategy_workflows.SemanticCompiler import ASTNode
from strategy_workflows.PlantedSignal import Segments, formula_to_dict, mean_reversion_formula
from utilities.AppConfig import MIN_TRADES, REWARD_MODES, REWARD_WEIGHTS

RANK_IC = 0.06
S_IC = min(1.0, RANK_IC / REWARD_WEIGHTS['max_ic'])


def _tree(window=10, z=1.0, inner=None):
    if inner is None:
        inner = ASTNode(name="sub", children=[
            ASTNode(name="pv_close"),
            ASTNode(name="ts_mean", children=[ASTNode(name="pv_close")], window=8)])
    return ASTNode(name="normalized_template", children=[
        inner, ASTNode(name="window", value=window), ASTNode(name="z_score", value=z)])


def _engine(data, mode):
    return MCTSEngine(timeframe='60m', data=data, seed=1, reward_mode=mode)


def _candidate(engine, tree):
    desc = describe_candidate(tree)
    _, direction, _ = engine.evaluate_expression(tree)
    return {'expr': desc['expr'], 'template': desc['template'], 'window': desc['window'],
            'z_score': desc['z_score_threshold'], 'threshold_upper': desc['threshold_upper'],
            'threshold_lower': desc['threshold_lower'], 'direction': direction}


# --- "gated" / "soft" regression ------------------------------------------------------------------------
# Expected values were produced by the code before the "sharpe" mode existed, on dummy_ohlcv_data.

GATED_SOFT_EXPECTED = {
    # (mode, window, z): (reward, rank_ic)
    ('gated', 5, 0.5): (0.6306503127438765, -0.011493867278953719),
    ('gated', 10, 1.0): (-10.0, None),
    ('gated', 20, 0.25): (0.6306503127438765, -0.011493867278953719),
    ('soft', 5, 0.5): (0.6306503127438765, -0.011493867278953719),
    ('soft', 10, 1.0): (0.030650312743876584, -0.011493867278953719),
    ('soft', 20, 0.25): (0.6306503127438765, -0.011493867278953719),
}
SPAN_EXPECTED = {'gated': -10.0, 'soft': 0.027948178216015914}


@pytest.mark.parametrize("key", list(GATED_SOFT_EXPECTED))
def test_gated_and_soft_rewards_are_unchanged(dummy_ohlcv_data, key):
    mode, window, z = key
    reward, _, metrics = _engine(dummy_ohlcv_data, mode).evaluate_expression(_tree(window, z))
    expected_reward, expected_ic = GATED_SOFT_EXPECTED[key]
    assert reward == pytest.approx(expected_reward, abs=1e-12)
    if expected_ic is None:
        assert 'rank_ic' not in metrics
    else:
        assert metrics['rank_ic'] == pytest.approx(expected_ic, abs=1e-12)


@pytest.mark.parametrize("mode", ["gated", "soft"])
def test_gated_and_soft_score_on_span_are_unchanged(dummy_ohlcv_data, mode):
    engine = _engine(dummy_ohlcv_data, mode)
    candidate = _candidate(engine, _tree(10, 1.0))
    index = dummy_ohlcv_data.index
    value = engine.score_on_span(candidate, dummy_ohlcv_data, str(index[300]), str(index[899]))
    assert value == pytest.approx(SPAN_EXPECTED[mode], abs=1e-12)


def test_sharpe_is_a_registered_mode_and_default_is_unchanged():
    from utilities.AppConfig import REWARD_MODE
    assert REWARD_MODES == ("gated", "soft", "sharpe")
    assert REWARD_MODE == "gated" and REWARD_WEIGHTS['max_sharpe'] == 3.0


# --- "sharpe" reward formula ----------------------------------------------------------------------------


def _reward(data, monkeypatch, mode, trades, sharpe, calmar=0.1):
    metrics = {'total_trades': trades, 'calmar_ratio': calmar, 'sharpe_ratio': sharpe}
    monkeypatch.setattr('strategy_workflows.MCTSEngine.compute_metrics', lambda result: dict(metrics))
    monkeypatch.setattr(MCTSEngine, 'compute_rank_ic', lambda self, alpha, close: RANK_IC)
    engine = _engine(data, mode)
    return engine.evaluate_expression(_tree())[0], engine


def test_sharpe_reward_formula(dummy_ohlcv_data, monkeypatch):
    reward, engine = _reward(dummy_ohlcv_data, monkeypatch, "sharpe", trades=30, sharpe=1.5)
    assert reward == pytest.approx(0.6 * 1.5 / 3.0 + 0.4 * S_IC)
    assert engine.gated_evaluation_count == 0


def test_sharpe_term_is_capped_at_one(dummy_ohlcv_data, monkeypatch):
    reward, _ = _reward(dummy_ohlcv_data, monkeypatch, "sharpe", trades=30, sharpe=9.0)
    assert reward == pytest.approx(0.6 + 0.4 * S_IC)


@pytest.mark.parametrize("sharpe", [-1.0, 0.0, None, float('nan')])
def test_sharpe_term_is_zero_for_non_positive_or_missing_sharpe(dummy_ohlcv_data, monkeypatch, sharpe):
    reward, _ = _reward(dummy_ohlcv_data, monkeypatch, "sharpe", trades=30, sharpe=sharpe, calmar=5.0)
    assert reward == pytest.approx(0.4 * S_IC)


def test_sharpe_term_is_zero_below_min_trades(dummy_ohlcv_data, monkeypatch):
    reward, _ = _reward(dummy_ohlcv_data, monkeypatch, "sharpe", trades=MIN_TRADES - 1, sharpe=2.5)
    assert reward == pytest.approx(0.4 * S_IC)
    reward, _ = _reward(dummy_ohlcv_data, monkeypatch, "sharpe", trades=MIN_TRADES, sharpe=2.5)
    assert reward == pytest.approx(0.6 * 2.5 / 3.0 + 0.4 * S_IC)


def test_sharpe_reward_ignores_the_calmar_gate(dummy_ohlcv_data, monkeypatch):
    low, _ = _reward(dummy_ohlcv_data, monkeypatch, "sharpe", trades=30, sharpe=1.5, calmar=0.2)
    high, _ = _reward(dummy_ohlcv_data, monkeypatch, "sharpe", trades=30, sharpe=1.5, calmar=9.0)
    assert low != -10.0 and low == pytest.approx(high)
    gated, _ = _reward(dummy_ohlcv_data, monkeypatch, "gated", trades=30, sharpe=1.5, calmar=0.2)
    assert gated == -10.0


def test_sharpe_mode_scores_evaluation_errors_as_minus_ten(dummy_ohlcv_data, monkeypatch):
    def boom(result):
        raise RuntimeError("metrics failed")
    monkeypatch.setattr('strategy_workflows.MCTSEngine.compute_metrics', boom)
    engine = _engine(dummy_ohlcv_data, "sharpe")
    assert engine.evaluate_expression(_tree())[0] == -10.0
    assert engine.failed_evaluation_count == 1


# --- IC input of "sharpe" mode --------------------------------------------------------------------------


@pytest.fixture
def trending_signal_frame():
    """Volume = linear trend + a stationary signal that drives the next bar's return."""
    rng = np.random.default_rng(5)
    n = 3000
    signal = rng.normal(size=n)
    ret = np.zeros(n)
    ret[1:] = 0.003 * signal[:-1] + 0.001 * rng.normal(size=n - 1)
    close = 1000.0 * np.cumprod(1.0 + ret)
    index = pd.date_range('2024-01-01', periods=n, freq='1h')
    return pd.DataFrame({'Open': close, 'High': close * 1.001, 'Low': close * 0.999, 'Close': close,
                         'Volume': 1000.0 + 1.0 * np.arange(n) + 50.0 * signal}, index=index)


WINDOW = 20


def _ic_tree():
    return _tree(window=WINDOW, z=0.5, inner=ASTNode(name="pv_volume"))


def test_sharpe_normalized_ic_is_taken_on_the_zscore(trending_signal_frame, monkeypatch):
    frame = trending_signal_frame
    engine = _engine(frame, "sharpe")
    seen = []
    original = MCTSEngine.compute_rank_ic

    def spy(self, alpha, close):
        seen.append(alpha.copy())
        return original(self, alpha, close)

    monkeypatch.setattr(MCTSEngine, 'compute_rank_ic', spy)
    _, _, metrics = engine.evaluate_expression(_ic_tree())
    expected = ts_zscore(frame['Volume'], WINDOW)
    pd.testing.assert_series_equal(seen[0], expected.astype(np.float64), check_names=False)
    raw_ic = original(engine, frame['Volume'], frame['Close'])
    assert abs(raw_ic) < 0.1 < 0.25 < abs(metrics['rank_ic'])


def test_soft_normalized_ic_stays_on_the_raw_alpha(trending_signal_frame):
    frame = trending_signal_frame
    engine = _engine(frame, "soft")
    _, _, metrics = engine.evaluate_expression(_ic_tree())
    assert metrics['rank_ic'] == pytest.approx(engine.compute_rank_ic(frame['Volume'], frame['Close']))


@pytest.mark.parametrize("kind", ["ratio", "boolean"])
def test_sharpe_ratio_and_boolean_ic_stay_on_the_raw_alpha(trending_signal_frame, monkeypatch, kind):
    frame = trending_signal_frame
    engine = _engine(frame, "sharpe")
    seen = []
    original = MCTSEngine.compute_rank_ic

    def spy(self, alpha, close):
        seen.append(alpha.copy())
        return original(self, alpha, close)

    monkeypatch.setattr(MCTSEngine, 'compute_rank_ic', spy)
    volume = ASTNode(name="pv_volume")
    if kind == "ratio":
        tree = ASTNode(name="ratio_template", children=[
            volume, ASTNode(name="threshold_upper", value=1100.0), ASTNode(name="threshold_lower", value=900.0)])
        expected = frame['Volume']
    else:
        mean = ASTNode(name="ts_mean", children=[ASTNode(name="pv_volume")], window=8)
        tree = ASTNode(name="greater_than", children=[volume, mean])
        expected = frame['Volume'] > frame['Volume'].rolling(8).mean()
    engine.evaluate_expression(tree)
    assert seen[0].astype(np.float64).equals(expected.astype(np.float64))


def test_sharpe_score_on_span_uses_the_zscore_ic(trending_signal_frame, monkeypatch):
    frame = trending_signal_frame
    engine = _engine(frame, "sharpe")
    candidate = _candidate(engine, _ic_tree())
    seen = []
    original = MCTSEngine.compute_rank_ic

    def spy(self, alpha, close):
        seen.append(alpha.copy())
        return original(self, alpha, close)

    monkeypatch.setattr(MCTSEngine, 'compute_rank_ic', spy)
    start, end = str(frame.index[1000]), str(frame.index[2500])
    engine.score_on_span(candidate, frame, start, end)
    bars = frame.loc[start:end].index
    expected = ts_zscore(frame['Volume'], WINDOW).loc[bars].astype(np.float64)   # warm-up comes from before start
    pd.testing.assert_series_equal(seen[0], expected, check_names=False)


# --- oracle ---------------------------------------------------------------------------------------------


def test_oracle_split_rewards_work_for_the_sharpe_mode(trending_signal_frame):
    import strategy_workflows.RunPlantedSignal as run
    frame = trending_signal_frame
    formula = mean_reversion_formula()
    segments = Segments(train_end='2024-02-15', search_end='2024-04-30', eval_end='2024-05-01')
    engine = MCTSEngine(timeframe='60m', data=frame.loc[:segments.train_end], seed=1, reward_mode='sharpe')
    out = run.planted_split_rewards(engine, formula, frame, segments)
    assert set(out) == {'train', 'validation'} and out['train'] > -10.0 and np.isfinite(out['validation'])


def test_oracle_writes_the_sharpe_columns_and_keeps_the_old_ones(tmp_path, monkeypatch):
    import argparse
    import strategy_workflows.RunPlantedSignal as run
    base = _planted_base()
    formula = mean_reversion_formula()
    formula_file = tmp_path / 'formula.json'
    formula_file.write_text(json.dumps(formula_to_dict(formula)), encoding='utf-8')
    monkeypatch.setattr(run, 'load_base', lambda segments: base)
    parser = argparse.ArgumentParser()
    run.add_planted_parser(parser.add_subparsers(dest='command'))
    args = parser.parse_args(['planted', 'oracle', '--out-dir', str(tmp_path), '--formula', str(formula_file),
                              '--strengths', '0.0', '--seeds', '1', '--workers', '1'])
    run.step_oracle(args)
    frame = pd.read_csv(tmp_path / 'oracle.csv')
    assert list(frame.columns) == run.ORACLE_FIELDS
    for old in ('reward_gated', 'reward_soft', 'z_gated', 'z_soft', 'calmar', 'trades', 'rank_ic',
                'reward_soft_train', 'reward_soft_val'):
        assert old in frame.columns
    row = frame.iloc[0]
    for new in ('reward_sharpe', 'z_sharpe', 'reward_sharpe_train', 'reward_sharpe_val'):
        assert np.isfinite(row[new])
    assert row['reward_sharpe'] > -10.0 and row['reward_sharpe_val'] > -10.0   # no gate in "sharpe" mode


def test_search_cli_accepts_every_reward_mode(tmp_path):
    import argparse
    import strategy_workflows.RunPlantedSignal as run
    parser = argparse.ArgumentParser()
    run.add_planted_parser(parser.add_subparsers(dest='command'))
    for mode in REWARD_MODES:
        args = parser.parse_args(['planted', 'search', '--out-dir', str(tmp_path), '--reward-mode', mode])
        assert args.reward_mode == mode


def test_summary_works_on_sharpe_runs():
    import strategy_workflows.RunPlantedSignal as run
    rows = [{'reward_mode': 'sharpe', 'strength': s, 'seed': seed, 'iterations': 100, 'ic_search': s, 'ic_eval': s,
             'exact': False, 'near': seed == 1, 'oos_sharpe': 0.5} for s in (0.0, 0.05) for seed in (1, 2)]
    summary = run.summarize_runs(pd.DataFrame(rows))
    assert set(summary['reward_mode']) == {'sharpe'} and list(summary['n_runs']) == [2, 2]
    assert any(line.startswith('sharpe IC 0.05') for line in run.criteria_report(summary))


def _planted_base():
    index = pd.date_range('2018-08-13', '2020-12-31', freq='4h')
    rng = np.random.default_rng(11)
    close = 1000.0 * np.cumprod(1.0 + np.clip(rng.standard_t(3, len(index)) * 0.002, -0.05, 0.05))
    return pd.DataFrame({'Open': close * 0.999, 'High': close * 1.002, 'Low': close * 0.998,
                         'Close': close, 'Volume': rng.uniform(1000, 5000, len(index))}, index=index)
