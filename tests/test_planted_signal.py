import numpy as np
import pandas as pd
import pytest

from strategy_workflows.MCTSEngine import MCTSEngine
from strategy_workflows.PlantedSignal import (
    PLANTED_FORMULA, PlantedFormula, assert_in_search_space, build_ohlcv_from_returns,
    build_planted_data, calibrate_beta, can_express, search_ic_for_seed, combine_positions, is_exact_recovery, is_near_recovery,
    is_verbatim, parse_expression, permute_returns, plant_signal, realized_ic, spearman_abs,
    split_bars, top_candidates,
)
from strategy_workflows.RunPlantedSignal import (
    DEFAULT_STRENGTHS, annotate_blueprints, summarize_runs, criteria_report,
)
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler

FORMULA = PLANTED_FORMULA
PERIODS = [2, 3, 5, 10]
WINDOWS = [2, 3, 5, 7, 10]


def synthetic_eps(n, seed=0, scale=0.003):
    eps = np.random.default_rng(seed).normal(0.0, scale, n)
    eps[0] = 0.0
    return eps


def plant(eps, ic, sigma=0.003):
    beta = ic / np.sqrt(1.0 - ic ** 2)
    return plant_signal(eps, np.full(len(eps), sigma), 1000.0, beta, FORMULA.signal_last, FORMULA.lookback)


# ─── Placebo base ────────────────────────────────────────────────────────

def test_permutation_keeps_return_multiset_and_bar_records(dummy_ohlcv_data):
    bars = split_bars(dummy_ohlcv_data)
    half = len(bars) // 2
    rng = np.random.default_rng(3)
    first = permute_returns(bars.iloc[:half], rng, keep_first=True)
    second = permute_returns(bars.iloc[half:], rng)

    for original, permuted in ((bars.iloc[:half], first), (bars.iloc[half:], second)):
        assert np.array_equal(np.sort(original['ret'].to_numpy()), np.sort(permuted['ret'].to_numpy()))
        assert permuted.index.equals(original.index)
        # Each permuted row must be one whole original row: Volume and shape travel with the return.
        original_rows = {tuple(r) for r in original.to_numpy()}
        assert {tuple(r) for r in permuted.to_numpy()} == original_rows
    assert not np.array_equal(first['ret'].to_numpy(), bars['ret'].iloc[:half].to_numpy())
    assert first.iloc[0].equals(bars.iloc[0])


def test_rebuilt_ohlcv_keeps_shape_and_hits_original_end_price(dummy_ohlcv_data):
    base = dummy_ohlcv_data
    bars = split_bars(base)
    perm = permute_returns(bars, np.random.default_rng(1), keep_first=True)
    rebuilt = build_ohlcv_from_returns(perm, perm['ret'].to_numpy(), float(base['Close'].iloc[0]))
    assert rebuilt['Close'].iloc[0] == base['Close'].iloc[0]
    # Product of (1 + r) does not depend on order.
    assert rebuilt['Close'].iloc[-1] == pytest.approx(base['Close'].iloc[-1], rel=1e-9)
    assert (rebuilt['High'] >= rebuilt['Low']).all()
    assert np.allclose(rebuilt['High'] / rebuilt['Close'], perm['high_ratio'])
    assert np.array_equal(rebuilt['Volume'].to_numpy(), perm['Volume'].to_numpy())


# ─── Planting ────────────────────────────────────────────────────────────

def test_ic_zero_returns_equal_permuted_returns_exactly():
    eps = synthetic_eps(2000)
    result = plant(eps, 0.0)
    assert np.array_equal(result.returns, eps)


def test_signal_matches_full_series_recomputation():
    result = plant(synthetic_eps(3000), 0.05)
    closes = pd.Series(result.closes)
    expected = FORMULA.signal_series(closes).to_numpy()
    assert np.array_equal(np.isnan(expected), np.isnan(result.signal))
    assert np.allclose(expected[~np.isnan(expected)], result.signal[~np.isnan(result.signal)], atol=1e-9)


def test_planting_does_not_look_ahead():
    n, t = 3000, 1500
    eps = synthetic_eps(n)
    altered = eps.copy()
    altered[t + 1:] = np.random.default_rng(99).normal(0.0, 0.003, n - t - 1)

    a, b = plant(eps, 0.05), plant(altered, 0.05)
    assert np.array_equal(a.signal[:t + 1], b.signal[:t + 1], equal_nan=True)
    assert np.array_equal(a.closes[:t + 1], b.closes[:t + 1])
    assert np.array_equal(a.returns[:t + 1], b.returns[:t + 1])
    assert not np.array_equal(a.closes[t + 1:], b.closes[t + 1:])


def test_realized_ic_near_target():
    n = 30_000
    result = plant(synthetic_eps(n, seed=5), 0.05)
    ic = realized_ic(pd.Series(result.signal), pd.Series(result.closes))
    # Standard error is about 1/sqrt(n) = 0.006, plus a small variance mismatch of the signal.
    assert abs(ic - 0.05) < 0.02
    null = plant(synthetic_eps(n, seed=5), 0.0)
    assert abs(realized_ic(pd.Series(null.signal), pd.Series(null.closes))) < 0.02


def heavy_tailed_eps(n, seed=0):
    eps = np.random.default_rng(seed).standard_t(3, n) * 0.002
    eps[0] = 0.0
    return eps


def realized_ic_for_beta(eps, sigma, beta):
    result = plant_signal(eps, sigma, 1000.0, beta, FORMULA.signal_last, FORMULA.lookback)
    return realized_ic(pd.Series(result.signal), pd.Series(result.closes))


def heavy_tailed_base(n_days=70, seed=3):
    """Hourly OHLCV with student-t (df 3) returns; the search segment ends at the end of day 50."""
    n = n_days * 24
    rng = np.random.default_rng(seed)
    close = 1000.0 * np.cumprod(1.0 + np.clip(rng.standard_t(3, n) * 0.002, -0.05, 0.05))
    index = pd.date_range('2020-01-01', periods=n, freq='h')
    return pd.DataFrame({'Open': close * 0.999, 'High': close * 1.002, 'Low': close * 0.998,
                         'Close': close, 'Volume': rng.uniform(1000, 5000, n)}, index=index)


CAL_SEEDS = range(1001, 1006)


def test_calibration_hits_mean_target_with_nonnegative_beta_and_is_deterministic():
    base = heavy_tailed_base()
    search_end = str(base.index[50 * 24 - 1].date())
    result = calibrate_beta(base, search_end, 0.05, seeds=CAL_SEEDS, tolerance=0.004)
    assert result.beta > 0.0
    assert abs(result.mean_ic - 0.05) <= 0.004
    # Recompute the mean independently at the returned beta.
    bars, n_search = split_bars(base), len(base.loc[:search_end])
    recomputed = np.mean([search_ic_for_seed(bars, n_search, float(base['Close'].iloc[0]), result.beta, sd)
                          for sd in CAL_SEEDS])
    assert recomputed == pytest.approx(result.mean_ic)
    again = calibrate_beta(base, search_end, 0.05, seeds=CAL_SEEDS, tolerance=0.004)
    assert again.beta == result.beta
    assert calibrate_beta(base, search_end, 0.0, seeds=CAL_SEEDS).beta == 0.0


def test_calibration_does_not_chase_chance_ic_with_negative_beta():
    # A target below the placebo's chance mean IC must leave beta at 0, never negative.
    base = heavy_tailed_base()
    search_end = str(base.index[50 * 24 - 1].date())
    result = calibrate_beta(base, search_end, 0.0005, seeds=CAL_SEEDS, tolerance=0.01)
    assert result.beta == 0.0


def test_get_beta_caches_in_calibration_json(tmp_path, monkeypatch):
    import strategy_workflows.RunPlantedSignal as run
    calls = []

    def fake(base, search_end, strength, formula, workers=1):
        calls.append(strength)
        return run.Calibration(0.03, 0.05, 0.01, [1001], 3)

    monkeypatch.setattr(run, 'calibrate_beta', fake)
    base = heavy_tailed_base()
    assert run.get_beta(base, 0.05, str(tmp_path)) == 0.03
    assert run.get_beta(base, 0.05, str(tmp_path)) == 0.03
    assert run.get_beta(base, 0.0, str(tmp_path)) == 0.0
    assert calls == [0.05]
    other = base.copy()
    other['Close'] = other['Close'] * 1.01
    run.get_beta(other, 0.05, str(tmp_path))
    assert calls == [0.05, 0.05]


def test_realized_ic_matches_engine_definition(dummy_ohlcv_data):
    engine = MCTSEngine(timeframe='60m', data=dummy_ohlcv_data, seed=1)
    close = dummy_ohlcv_data['Close']
    alpha = FORMULA.signal_series(close)
    assert realized_ic(alpha, close) == pytest.approx(engine.compute_rank_ic(alpha, close))


def test_build_planted_data_is_continuous_and_reproducible(dummy_ohlcv_data):
    search_end = '2024-01-07'
    a = build_planted_data(dummy_ohlcv_data, search_end, 0.05, seed=4, beta=0.02)
    b = build_planted_data(dummy_ohlcv_data, search_end, 0.05, seed=4, beta=0.02)
    c = build_planted_data(dummy_ohlcv_data, search_end, 0.05, seed=5, beta=0.02)
    assert a.full.equals(b.full)
    assert not a.full['Close'].equals(c.full['Close'])
    assert len(a.search) + len(a.evaluation) == len(dummy_ohlcv_data)
    assert a.search.index.max() <= pd.Timestamp('2024-01-08')
    assert a.evaluation.index.min() > a.search.index.max()
    assert (a.full['Close'] > 0).all()
    # The evaluation segment's first return is measured from the search segment's last close.
    gap_return = a.evaluation['Close'].iloc[0] / a.search['Close'].iloc[-1] - 1.0
    assert abs(gap_return) < 0.05


def test_formula_is_in_search_space_at_60m(dummy_ohlcv_data):
    engine = MCTSEngine(timeframe='60m', data=dummy_ohlcv_data, seed=1)
    assert_in_search_space(engine)
    with pytest.raises(ValueError):
        assert_in_search_space(engine, PlantedFormula(period=11, window=10))
    assert FORMULA.expr == "(close - ts_mean(close, 10))"


# ─── Top-5 combination ───────────────────────────────────────────────────

def test_combine_positions_uses_equal_weights():
    index = pd.RangeIndex(4)
    series = [pd.Series([0.2, 0.0, -0.2, 0.2], index=index),
              pd.Series([0.2, 0.2, 0.2, 0.0], index=index),
              pd.Series([0.0, 0.0, -0.2, -0.2], index=index)]
    combined = combine_positions(series)
    assert np.allclose(combined, [0.4 / 3, 0.2 / 3, -0.2 / 3, 0.0])
    two = combine_positions(series[:2])
    assert np.allclose(two, (series[0] + series[1]) / 2)
    with pytest.raises(ValueError):
        combine_positions([])


def test_top_candidates_picks_best_distinct_and_skips_failures():
    def cand(expr, reward, window=10):
        return {'expr': expr, 'reward': reward, 'template': 'NORMALIZED', 'window': window,
                'z_score': 1.0, 'direction': 1.0}
    board = [cand('a', 0.3), cand('b', 0.9), cand('a', 0.3), cand('c', -10.0), cand('d', 0.5),
             cand('e', 0.1), cand('f', 0.2), cand('g', 0.05)]
    top = top_candidates(board, k=5)
    assert [c['expr'] for c in top] == ['b', 'd', 'a', 'f', 'e']
    assert [c['expr'] for c in top_candidates(board[:3], k=5)] == ['b', 'a']


# ─── Blueprint coverage ──────────────────────────────────────────────────

def compile_(text):
    return SemanticCompiler().compile_blueprint(text)


def test_can_express_hole_blueprint_and_rejects_unrelated():
    target = FORMULA.expr_ast()
    assert can_express(compile_("sub(?, ts_mean(?))"), target)
    assert can_express(compile_("sub(?, ?)"), target)
    assert can_express(compile_("sub(pv_close, ts_mean(?))"), target)
    assert not can_express(compile_("add(?, ts_mean(?))"), target)
    assert not can_express(compile_("sub(?, ts_max(?))"), target)
    assert not can_express(compile_("ts_corr(?, ?)"), target)          # RATIO template
    assert not can_express(compile_("greater_than(?, ?)"), target)     # BOOLEAN template
    assert not can_express(compile_("sub(pv_volume, ts_mean(?))"), target)


def test_can_express_root_sub_swap_only():
    target = FORMULA.expr_ast()
    assert can_express(compile_("sub(ts_mean(?), ?)"), target)
    assert can_express(compile_("sub(ts_mean(pv_close), pv_close)"), target)
    assert not can_express(compile_("sub(ts_mean(pv_close), pv_open)"), target)
    assert not can_express(compile_("add(ts_mean(?), ?)"), target)
    # A swapped sub below the root does not match.
    nested = ASTNode(name='ts_mean', children=[target], window=10)
    assert can_express(compile_("ts_mean(sub(pv_close, ts_mean(?)))"), nested)
    assert not can_express(compile_("ts_mean(sub(ts_mean(?), pv_close))"), nested)


def test_verbatim_means_no_hole_left():
    target = FORMULA.expr_ast()
    assert is_verbatim(compile_("sub(ts_mean(pv_close, 10), pv_close)"), target)
    assert is_verbatim(compile_("sub(pv_close, ts_mean(pv_close, 10))"), target)
    assert not is_verbatim(compile_("sub(?, ts_mean(?))"), target)


def test_can_express_respects_depth_limit():
    target = FORMULA.expr_ast()
    # '?' under two extra operators sits at depth 3; the target subtree below it needs more room.
    assert not can_express(compile_("ts_mean(ts_mean(?))"), target)
    assert can_express(compile_("sub(?, ts_mean(?))"), target, max_depth=4)


def test_annotate_blueprints_flags():
    flags = annotate_blueprints([
        {'name': 'hole', 'macro_blueprint': 'sub(?, ts_mean(?))'},
        {'name': 'other', 'macro_blueprint': 'add(?, ts_max(?))'},
        {'name': 'same', 'macro_blueprint': 'sub(pv_close, ts_mean(pv_close, 10))'},
    ])
    assert [(f['can_express'], f['verbatim']) for f in flags] == [(True, False), (False, False), (True, True)]


# ─── Recovery ────────────────────────────────────────────────────────────

def candidate(expr="(close - ts_mean(close, 10))", window=10, direction=1.0, template='NORMALIZED'):
    return {'expr': expr, 'window': window, 'direction': direction, 'template': template}


def exact(c):
    return is_exact_recovery(c, FORMULA, PERIODS, WINDOWS)


def test_exact_recovery_cases():
    assert exact(candidate())
    assert exact(candidate("(close - ts_mean(close, 5))"))            # one step in periods
    assert exact(candidate(window=7))                                  # one step in z-score windows
    assert not exact(candidate("(close - ts_mean(close, 3))"))        # two steps
    assert not exact(candidate(window=5))                              # two steps
    assert not exact(candidate(template='RATIO'))
    assert not exact(candidate("(close - ts_mean(open_, 10))"))        # different field
    assert exact(candidate("(ts_mean(close, 10) - close)", direction=-1.0))   # root sub swapped (-A), traded short
    assert not exact(candidate("(ts_mean(close, 10) - close)", direction=1.0))  # -A long is the opposite signal
    assert not exact(candidate(direction=-1.0))                        # A short is the opposite signal
    assert not exact(candidate("(ts_mean(close, 10) + close)"))        # add is not special-cased
    assert not exact(candidate("(close - ts_max(close, 10))"))
    assert not exact(candidate("(close - ts_mean(close, 4))"))         # window outside the ladder


def test_parse_expression_drops_division_guard():
    assert parse_expression("(close / (volume + 1e-8))") == parse_expression("(close / volume)")
    with pytest.raises(ValueError):
        parse_expression("close ** 2")


def test_near_recovery_uses_absolute_rank_correlation():
    rng = np.random.default_rng(0)
    a = pd.Series(rng.normal(size=500))
    assert spearman_abs(a, a * 3 + 1) == pytest.approx(1.0)
    assert spearman_abs(a, -a) == pytest.approx(1.0)
    assert spearman_abs(a, pd.Series(rng.normal(size=500))) < 0.2
    assert spearman_abs(a, pd.Series(1.0, index=a.index)) == 0.0
    assert is_near_recovery(0.7) and not is_near_recovery(0.699)


# ─── Summary ─────────────────────────────────────────────────────────────

def test_summary_keeps_last_rerun_and_criteria():
    rows = []
    for seed in range(1, 6):
        for strength, near in ((0.05, seed <= 3), (0.0, seed <= 1)):
            rows.append({'reward_mode': 'soft', 'strength': strength, 'seed': seed, 'iterations': 100,
                         'ic_search': 0.1, 'ic_eval': 0.05, 'exact': False, 'near': near, 'oos_sharpe': 1.0})
    # A rerun of one key replaces the earlier row.
    rows.append({'reward_mode': 'soft', 'strength': 0.05, 'seed': 5, 'iterations': 100,
                 'ic_search': 0.1, 'ic_eval': 0.05, 'exact': True, 'near': True, 'oos_sharpe': 3.0})
    summary = summarize_runs(pd.DataFrame(rows))
    top = summary[np.isclose(summary['strength'], 0.05)].iloc[0]
    assert top['n_runs'] == 5 and top['near_count'] == 4 and top['exact_count'] == 1
    assert top['oos_sharpe_mean'] == pytest.approx(1.4)
    lines = criteria_report(summary)
    assert any('IC 0.05' in l and 'PASS' in l for l in lines)
    assert any('IC 0.0' in l and 'PASS' in l for l in lines)
    assert DEFAULT_STRENGTHS == [0.0, 0.01, 0.02, 0.05]
