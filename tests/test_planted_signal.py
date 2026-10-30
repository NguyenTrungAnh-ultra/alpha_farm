import json

import numpy as np
import pandas as pd
import pytest

from strategy_workflows.MCTSEngine import MCTSEngine, describe_candidate
from strategy_workflows.PlantedSignal import (
    PlantedFormula, Segments, assert_in_search_space, build_ohlcv_from_returns,
    build_planted_data, calibrate_beta, can_express, search_ic_for_seed, combine_positions, formula_from_dict,
    formula_to_dict, is_exact_recovery, is_near_recovery, is_verbatim, mean_reversion_formula, parse_expression,
    permute_returns, plant_signal, realized_ic, select_planted_formula, shape_fields, spearman_abs, split_bars,
    distinct_expressions, rank_by_validation, top_candidates,
)
from strategy_workflows.RunPlantedSignal import (
    DEFAULT_STRENGTHS, annotate_blueprints, calibration_key, criteria_report, rank_leaderboard, summarize_runs,
)
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler

FORMULA = mean_reversion_formula()
PERIODS = [2, 3, 5, 10]
WINDOWS = [2, 3, 5, 7, 10]


def synthetic_eps(n, seed=0, scale=0.003):
    eps = np.random.default_rng(seed).normal(0.0, scale, n)
    eps[0] = 0.0
    return eps


def close_frame(closes):
    closes = pd.Series(closes).to_numpy()
    return pd.DataFrame({'Open': closes, 'High': closes, 'Low': closes, 'Close': closes, 'Volume': 1.0})


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
    expected = FORMULA.signal_series(close_frame(closes)).to_numpy()
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
    result = calibrate_beta(base, search_end, 0.05, FORMULA, seeds=CAL_SEEDS, tolerance=0.004)
    assert result.beta > 0.0
    assert abs(result.mean_ic - 0.05) <= 0.004
    # Recompute the mean independently at the returned beta.
    bars, n_search = split_bars(base), len(base.loc[:search_end])
    recomputed = np.mean([search_ic_for_seed(bars, n_search, float(base['Close'].iloc[0]), result.beta, sd, FORMULA)
                          for sd in CAL_SEEDS])
    assert recomputed == pytest.approx(result.mean_ic)
    again = calibrate_beta(base, search_end, 0.05, FORMULA, seeds=CAL_SEEDS, tolerance=0.004)
    assert again.beta == result.beta
    assert calibrate_beta(base, search_end, 0.0, FORMULA, seeds=CAL_SEEDS).beta == 0.0


def test_calibration_does_not_chase_chance_ic_with_negative_beta():
    # A target below the placebo's chance mean IC must leave beta at 0, never negative.
    base = heavy_tailed_base()
    search_end = str(base.index[50 * 24 - 1].date())
    result = calibrate_beta(base, search_end, 0.0005, FORMULA, seeds=CAL_SEEDS, tolerance=0.01)
    assert result.beta == 0.0


def test_get_beta_caches_in_calibration_json(tmp_path, monkeypatch):
    import strategy_workflows.RunPlantedSignal as run
    calls = []

    def fake(base, search_end, strength, formula, workers=1):
        calls.append(strength)
        return run.Calibration(0.03, 0.05, 0.01, [1001], 3)

    monkeypatch.setattr(run, 'calibrate_beta', fake)
    base = heavy_tailed_base()
    assert run.get_beta(base, 0.05, str(tmp_path), FORMULA) == 0.03
    assert run.get_beta(base, 0.05, str(tmp_path), FORMULA) == 0.03
    assert run.get_beta(base, 0.0, str(tmp_path), FORMULA) == 0.0
    assert calls == [0.05]
    other = base.copy()
    other['Close'] = other['Close'] * 1.01
    run.get_beta(other, 0.05, str(tmp_path), FORMULA)
    assert calls == [0.05, 0.05]
    # A different expression or z-score window is a different calibration.
    run.get_beta(base, 0.05, str(tmp_path), mean_reversion_formula(period=5))
    run.get_beta(base, 0.05, str(tmp_path), mean_reversion_formula(window=7))
    assert calls == [0.05, 0.05, 0.05, 0.05]
    run.get_beta(base, 0.05, str(tmp_path), mean_reversion_formula(period=5))
    assert len(calls) == 4
    assert calibration_key(base, 0.05, FORMULA) != calibration_key(base, 0.05, two_slot_formula())


def test_realized_ic_matches_engine_definition(dummy_ohlcv_data):
    engine = MCTSEngine(timeframe='60m', data=dummy_ohlcv_data, seed=1)
    close = dummy_ohlcv_data['Close']
    alpha = FORMULA.signal_series(dummy_ohlcv_data)
    assert realized_ic(alpha, close) == pytest.approx(engine.compute_rank_ic(alpha, close))


def test_build_planted_data_is_continuous_and_reproducible(dummy_ohlcv_data):
    search_end = '2024-01-07'
    a = build_planted_data(dummy_ohlcv_data, search_end, 0.05, seed=4, beta=0.02, formula=FORMULA)
    b = build_planted_data(dummy_ohlcv_data, search_end, 0.05, seed=4, beta=0.02, formula=FORMULA)
    c = build_planted_data(dummy_ohlcv_data, search_end, 0.05, seed=5, beta=0.02, formula=FORMULA)
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
    assert_in_search_space(engine, FORMULA)
    with pytest.raises(ValueError):
        assert_in_search_space(engine, mean_reversion_formula(period=11))
    with pytest.raises(ValueError):
        assert_in_search_space(engine, mean_reversion_formula(window=11))
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
    flags = annotate_blueprints(blueprints=[
        {'name': 'hole', 'macro_blueprint': 'sub(?, ts_mean(?))'},
        {'name': 'other', 'macro_blueprint': 'add(?, ts_max(?))'},
        {'name': 'same', 'macro_blueprint': 'sub(pv_close, ts_mean(pv_close, 10))'},
    ], formula=FORMULA)
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
    assert DEFAULT_STRENGTHS == [0.0, 0.01, 0.02, 0.05, 0.1, 0.2]


# ─── Generic formulas and selection ──────────────────────────────────────

def two_slot_formula(z_window=5):
    """ts_mean(pv_high - ts_mean(pv_close, 5), 3): two fields, nested windows."""
    tree = ASTNode(name='ts_mean', window=3, children=[
        ASTNode(name='sub', children=[
            ASTNode(name='pv_high'),
            ASTNode(name='ts_mean', window=5, children=[ASTNode(name='pv_close')]),
        ])])
    return PlantedFormula(tree=tree, z_window=z_window, source='two_slot')


def volume_formula():
    tree = ASTNode(name='mult', children=[
        ASTNode(name='sub', children=[ASTNode(name='pv_open'), ASTNode(name='pv_low')]),
        ASTNode(name='pv_volume')])
    return PlantedFormula(tree=tree, z_window=3, source='volume')


def synthetic_shape(n, seed=0):
    rng = np.random.default_rng(seed)
    bars = pd.DataFrame({
        'open_ratio': rng.uniform(0.998, 1.002, n), 'high_ratio': rng.uniform(1.0, 1.01, n),
        'low_ratio': rng.uniform(0.99, 1.0, n), 'Volume': rng.uniform(1000, 5000, n),
    })
    bars.loc[7, 'Volume'] = np.nan
    return bars


def test_formula_lookback_and_fields():
    two = two_slot_formula()
    assert two.expr == "ts_mean((high - ts_mean(close, 5)), 3)"
    assert two.lookback == (3 - 1) + (5 - 1) + 5          # nested windows, then the z-score window
    assert two.used_fields == ['close', 'high']
    assert two.windows == [3, 5]
    assert FORMULA.lookback == 10 + 10 - 1
    assert volume_formula().used_fields == ['low', 'open_', 'volume']


@pytest.mark.parametrize("make", [two_slot_formula, volume_formula])
def test_generic_trailing_signal_equals_full_series(make):
    formula = make()
    n = 1500
    bars = synthetic_shape(n)
    eps = synthetic_eps(n, seed=2)
    planted = plant_signal(eps, np.full(n, 0.003), 1000.0, 0.05, formula.signal_last, formula.lookback,
                           shape_fields(bars, formula))
    frame = build_ohlcv_from_returns(bars, planted.returns, 1000.0)
    expected = formula.signal_series(frame).to_numpy()
    assert np.array_equal(np.isnan(expected), np.isnan(planted.signal))
    ok = ~np.isnan(expected)
    assert ok.sum() > n - 50
    assert np.allclose(expected[ok], planted.signal[ok], rtol=1e-9, atol=1e-12)


def test_generic_planting_does_not_look_ahead():
    formula = two_slot_formula()
    n, t = 1200, 600
    bars = synthetic_shape(n, seed=1)
    eps = synthetic_eps(n, seed=3)
    altered = eps.copy()
    altered[t + 1:] = np.random.default_rng(7).normal(0.0, 0.003, n - t - 1)
    shape = shape_fields(bars, formula)
    a = plant_signal(eps, np.full(n, 0.003), 1000.0, 0.05, formula.signal_last, formula.lookback, shape)
    b = plant_signal(altered, np.full(n, 0.003), 1000.0, 0.05, formula.signal_last, formula.lookback, shape)
    assert np.array_equal(a.signal[:t + 1], b.signal[:t + 1], equal_nan=True)
    assert np.array_equal(a.closes[:t + 1], b.closes[:t + 1])
    assert not np.array_equal(a.closes[t + 1:], b.closes[t + 1:])


def test_build_planted_data_signal_matches_full_series_for_generic_formula(dummy_ohlcv_data):
    formula = two_slot_formula()
    data = build_planted_data(dummy_ohlcv_data, '2024-01-07', 0.05, seed=2, beta=0.05, formula=formula)
    expected = formula.signal_series(data.full)
    both = expected.notna() & data.signal.notna()
    assert (expected.isna() == data.signal.isna()).all()
    assert both.sum() > 900
    assert np.allclose(expected[both], data.signal[both], rtol=1e-9, atol=1e-12)


def test_formula_dict_roundtrip():
    formula = two_slot_formula()
    back = formula_from_dict(formula_to_dict(formula))
    assert back == formula and back.expr == formula.expr and back.windows == formula.windows
    broken = formula_to_dict(formula)
    broken['expression'] = "close"
    with pytest.raises(ValueError):
        formula_from_dict(broken)


def blueprint(name, text):
    return {'name': name, 'macro_blueprint': text}


@pytest.fixture
def engine_60m(dummy_ohlcv_data):
    return MCTSEngine(timeframe='60m', data=dummy_ohlcv_data, seed=1)


def test_select_skips_one_slot_non_normalized_and_verbatim(engine_60m):
    assert compile_("sub(?, ts_mean(?))").name == 'normalized_template'
    assert compile_("ts_corr(?, ?)").name != 'normalized_template'
    blueprints = [
        blueprint('one_slot', 'sub(pv_high, ts_mean(?))'),                        # 1 slot
        blueprint('ratio_root', 'ts_corr(?, ?)'),                                 # not NORMALIZED
        blueprint('boolean_root', 'greater_than(?, ?)'),                          # not NORMALIZED
        blueprint('spelled_out', 'sub(pv_close, ts_mean(pv_close, 10))'),         # 0 slots
        blueprint('verbatim_case', 'sub(?, ts_mean(?))'),                         # fills to the line above
        blueprint('good', 'mult(sub(ts_max(?), ts_min(?)), pv_volume)'),
        blueprint('later', 'add(?, ts_mean(?))'),
    ]
    formula, info = select_planted_formula(blueprints, engine_60m)
    assert formula.source == 'good'
    assert formula.expr == "((ts_max(close, 10) - ts_min(close, 10)) * volume)"
    assert formula.z_window == 10 and formula.windows == [10]
    assert formula.used_fields == ['close', 'volume']
    assert info['skipped_verbatim'] == ['verbatim_case'] and not info['adjusted']
    # Without the spelled-out blueprint, 'verbatim_case' is the first qualifying one.
    formula, _ = select_planted_formula([b for b in blueprints if b['name'] != 'spelled_out'], engine_60m)
    assert formula.source == 'verbatim_case' and formula.expr == "(close - ts_mean(close, 10))"


def test_select_first_qualifying_wins_and_none_fails_loudly(engine_60m):
    formula, _ = select_planted_formula(
        [blueprint('a', 'add(?, ts_mean(?))'), blueprint('b', 'mult(?, ts_max(?))')], engine_60m)
    assert formula.source == 'a' and formula.expr == "(close + ts_mean(close, 10))"
    with pytest.raises(ValueError, match="not loosened"):
        select_planted_formula([blueprint('x', 'sub(pv_high, ts_mean(?))'), blueprint('y', 'ts_corr(?, ?)')], engine_60m)
    with pytest.raises(ValueError, match="constant"):
        select_planted_formula([blueprint('degenerate', 'sub(?, ?)')], engine_60m)


def test_select_skips_constant_filled_formula(engine_60m):
    formula, info = select_planted_formula(
        [blueprint('flat', 'sub(?, ?)'), blueprint('next', 'add(?, ts_mean(?))')], engine_60m)
    assert formula.source == 'next' and formula.expr == "(close + ts_mean(close, 10))"
    assert info['skipped_constant'] == ['flat'] and info['skipped_verbatim'] == []


def test_select_keeps_formula_with_dead_term_but_not_constant(engine_60m):
    text = 'sub(ts_zscore(sub(pv_high, ?)), ts_zscore(sub(pv_close, ?)))'
    assert compile_(text).name == 'normalized_template'
    formula, info = select_planted_formula([blueprint('dead_term', text)], engine_60m)
    assert formula.source == 'dead_term' and info['skipped_constant'] == []


def test_select_uses_nearest_allowed_windows():
    from types import SimpleNamespace
    engine = SimpleNamespace(scaled_periods=[5, 14], scaled_window_search=[7, 12], max_depth=4)
    formula, info = select_planted_formula([blueprint('a', 'sub(?, ts_mean(?))')], engine)
    assert formula.windows == [14] and formula.z_window == 12 and info['adjusted']
    assert formula.expr == "(close - ts_mean(close, 14))"


def test_selected_formula_drives_recovery_checks(engine_60m):
    formula, _ = select_planted_formula([blueprint('g', 'sub(pv_high, ts_mean(?))'),
                                         blueprint('h', 'sub(ts_max(?), ts_mean(?))')], engine_60m)
    assert formula.expr == "(ts_max(close, 10) - ts_mean(close, 10))"
    good = candidate("(ts_max(close, 10) - ts_mean(close, 10))")
    assert is_exact_recovery(good, formula, PERIODS, WINDOWS)
    assert is_exact_recovery(candidate("(ts_max(close, 5) - ts_mean(close, 10))"), formula, PERIODS, WINDOWS)
    swapped = candidate("(ts_mean(close, 10) - ts_max(close, 10))", direction=-1.0)
    assert is_exact_recovery(swapped, formula, PERIODS, WINDOWS)
    assert not is_exact_recovery(candidate(), formula, PERIODS, WINDOWS)         # a different formula
    assert not is_exact_recovery(candidate("(ts_max(high, 10) - ts_mean(close, 10))"), formula, PERIODS, WINDOWS)
    assert can_express(compile_("sub(ts_max(?), ?)"), formula.expr_ast())
    assert not can_express(compile_("sub(ts_min(?), ?)"), formula.expr_ast())


# ─── Distinct top-k, train/validation split ──────────────────────────────

def test_top_candidates_has_k_distinct_expressions_and_keeps_best_params():
    def cand(expr, reward, window, z=1.0):
        return {'expr': expr, 'reward': reward, 'template': 'NORMALIZED', 'window': window,
                'z_score': z, 'direction': 1.0}
    board = [cand('a', 0.4, 5, 0.5), cand('a', 0.9, 10, 1.0), cand('a', 0.8, 3, 2.0), cand('b', 0.7, 5),
             cand('c', -10.0, 5), cand('c', 0.6, 7), cand('d', 0.5, 5)]
    top = top_candidates(board, k=3)
    assert [c['expr'] for c in top] == ['a', 'b', 'c']
    assert (top[0]['window'], top[0]['z_score'], top[0]['reward']) == (10, 1.0, 0.9)
    assert [c['expr'] for c in distinct_expressions(board)] == ['a', 'b', 'c', 'd']


def test_rank_by_validation_orders_by_validation_reward_and_ignores_train_order():
    candidates = [{'expr': e} for e in 'abcd']
    assert rank_by_validation(candidates, [0.1, 0.9, 0.5, 0.9]) == [1, 3, 2, 0]
    with pytest.raises(ValueError):
        rank_by_validation(candidates, [0.1])


def span_candidate(engine, tree):
    desc = describe_candidate(tree)
    _, direction, _ = engine.evaluate_expression(tree)
    return {'expr': desc['expr'], 'template': desc['template'], 'window': desc['window'],
            'z_score': desc['z_score_threshold'], 'threshold_upper': desc['threshold_upper'],
            'threshold_lower': desc['threshold_lower'], 'direction': direction}


def normalized_tree_for_test(z=0.5):
    return ASTNode(name='normalized_template', children=[
        FORMULA.expr_ast(), ASTNode(name='window', value=10), ASTNode(name='z_score', value=z)])


PRICE_COLUMNS = ['Open', 'High', 'Low', 'Close']


def test_score_on_span_over_whole_frame_equals_evaluate_expression(dummy_ohlcv_data):
    engine = MCTSEngine(timeframe='60m', data=dummy_ohlcv_data, seed=1, reward_mode='soft')
    tree = normalized_tree_for_test()
    reward, _, _ = engine.evaluate_expression(tree)
    candidate = span_candidate(engine, tree)
    index = dummy_ohlcv_data.index
    assert engine.score_on_span(candidate, dummy_ohlcv_data, str(index[0]), str(index[-1])) == pytest.approx(reward)


def test_score_on_span_uses_only_span_bars_but_keeps_warmup(dummy_ohlcv_data):
    engine = MCTSEngine(timeframe='60m', data=dummy_ohlcv_data, seed=1, reward_mode='soft')
    candidate = span_candidate(engine, normalized_tree_for_test())
    frame, index = dummy_ohlcv_data, dummy_ohlcv_data.index
    start, end = str(index[500]), str(index[899])
    base = engine.score_on_span(candidate, frame, start, end)
    cols = frame.columns.get_indexer(PRICE_COLUMNS)

    far = frame.copy()                      # huge values only on early train bars, well before the warm-up
    far.iloc[:300, cols] *= 1000.0
    assert engine.score_on_span(candidate, far, start, end) == pytest.approx(base)

    warm = frame.copy()                     # a change inside the warm-up (ts_mean 10 + z-score window 10)
    warm.iloc[495:500, cols] *= 1.5
    assert engine.score_on_span(candidate, warm, start, end) != pytest.approx(base)

    late = frame.copy()                     # bars after the span end do not matter either
    late.iloc[900:, cols] *= 7.0
    assert engine.score_on_span(candidate, late, start, end) == pytest.approx(base)


def test_score_on_span_scores_exactly_the_span_bars(dummy_ohlcv_data, monkeypatch):
    engine = MCTSEngine(timeframe='60m', data=dummy_ohlcv_data, seed=1, reward_mode='soft')
    candidate = span_candidate(engine, normalized_tree_for_test())
    index = dummy_ohlcv_data.index
    recorded = []
    original = engine._reward_over_directions

    def spy(alpha_val, rank_ic, df, desc, info, bars=None, directions=(1.0, -1.0)):
        recorded.append((bars, directions, len(df)))
        return original(alpha_val, rank_ic, df, desc, info, bars, directions)

    monkeypatch.setattr(engine, '_reward_over_directions', spy)
    engine.score_on_span(candidate, dummy_ohlcv_data, str(index[500]), str(index[899]))
    bars, directions, frame_len = recorded[0]
    assert bars[0] == index[500] and bars[-1] == index[899] and len(bars) == 400
    assert directions == (candidate['direction'],) and frame_len == len(index)


def test_rank_leaderboard_picks_by_validation_not_train():
    from types import SimpleNamespace
    board = [{'expr': e, 'reward': r} for e, r in (('a', 0.9), ('a', 0.8), ('b', 0.7), ('c', 0.6), ('d', 0.5))]
    val = {'a': 0.1, 'b': 0.5, 'c': 0.9, 'd': 0.3}
    engine = SimpleNamespace(get_best_candidates=lambda: board,
                             score_on_span=lambda c, frame, start, end: val[c['expr']])
    picked = rank_leaderboard(engine, None, Segments(), k=2)
    assert [c['expr'] for c in picked['ranked']] == ['a', 'b', 'c', 'd']
    assert [picked['ranked'][i]['expr'] for i in picked['chosen']] == ['c', 'b']


def planted_base():
    index = pd.date_range('2018-08-13', '2020-12-31', freq='4h')
    rng = np.random.default_rng(11)
    close = 1000.0 * np.cumprod(1.0 + np.clip(rng.standard_t(3, len(index)) * 0.002, -0.05, 0.05))
    return pd.DataFrame({'Open': close * 0.999, 'High': close * 1.002, 'Low': close * 0.998,
                         'Close': close, 'Volume': rng.uniform(1000, 5000, len(index))}, index=index)


def test_run_single_search_never_sees_bars_after_train_end(monkeypatch):
    import strategy_workflows.RunPlantedSignal as run
    base = planted_base()
    monkeypatch.setattr(run, 'load_base', lambda segments: base)
    seen = []

    class SpyEngine(MCTSEngine):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            seen.append(self.df.index.copy())

    monkeypatch.setattr(run, 'MCTSEngine', SpyEngine)
    task = {'reward_mode': 'soft', 'strength': 0.0, 'seed': 1, 'beta': 0.0, 'iterations': 15,
            'blueprints': [{'name': 'bp', 'macro_blueprint': 'sub(?, ts_mean(?))'}], 'formula': FORMULA,
            'segments': Segments()}
    row = run.run_single(task)
    assert len(seen) == 1
    assert seen[0].equals(base.index[base.index < pd.Timestamp('2020-01-01')])
    assert seen[0].max() <= pd.Timestamp('2019-12-31 23:59:59')
    assert row['n_ranked'] >= 1 and row['n_top'] == len(json.loads(row['top_exprs']))
    assert len(set(json.loads(row['top_exprs']))) == row['n_top']       # distinct expressions
    assert len(json.loads(row['top_val_rewards'])) == row['n_top']
    assert 1 <= row['closest_val_rank'] <= row['n_ranked'] and 1 <= row['closest_train_rank'] <= row['n_ranked']
    assert list(row) == run.RUN_FIELDS


def test_default_segments_equal_run_two_constants():
    seg = Segments()
    assert seg.to_dict() == {'search_start': '2018-08-13', 'train_end': '2019-12-31',
                             'search_end': '2020-06-30', 'eval_end': '2020-12-31'}
    assert seg.validation_start == '2020-01-01' and seg.eval_start == '2020-07-01'
    assert Segments.from_dict(seg.to_dict()) == seg


def test_segments_ordering_is_validated():
    for bad in (dict(train_end='2018-08-13'), dict(train_end='2020-06-30'), dict(search_end='2020-12-31'),
                dict(eval_end='2020-06-29'), dict(search_start='2020-01-01')):
        with pytest.raises(ValueError):
            Segments(**bad)
    long_run = Segments(train_end='2022-06-30', search_end='2023-12-31', eval_end='2024-12-31')
    assert long_run.validation_start == '2022-07-01' and long_run.eval_start == '2024-01-01'


CUSTOM_SEGMENTS = Segments(train_end='2019-06-30', search_end='2020-03-31', eval_end='2020-09-30')


def test_run_single_uses_the_segments_of_its_task_not_module_defaults(monkeypatch):
    # The task dict is the only thing a pool worker receives, so every date must come from it.
    import strategy_workflows.RunPlantedSignal as run
    base = planted_base()
    loaded, trains, spans, splits = [], [], [], []

    def fake_load(segments):
        loaded.append(segments)
        return base.loc[segments.search_start:segments.eval_end]

    class SpyEngine(MCTSEngine):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            trains.append(self.df.index.copy())

        def score_on_span(self, candidate, frame, start, end):
            spans.append((start, end))
            return super().score_on_span(candidate, frame, start, end)

    real_build = run.build_planted_data

    def spy_build(base_frame, search_end, *args, **kwargs):
        splits.append(search_end)
        return real_build(base_frame, search_end, *args, **kwargs)

    monkeypatch.setattr(run, 'load_base', fake_load)
    monkeypatch.setattr(run, 'MCTSEngine', SpyEngine)
    monkeypatch.setattr(run, 'build_planted_data', spy_build)
    task = {'reward_mode': 'soft', 'strength': 0.0, 'seed': 1, 'beta': 0.0, 'iterations': 15,
            'blueprints': [{'name': 'bp', 'macro_blueprint': 'sub(?, ts_mean(?))'}], 'formula': FORMULA,
            'segments': CUSTOM_SEGMENTS}
    run.run_single(task)
    assert loaded == [CUSTOM_SEGMENTS]
    assert splits == ['2020-03-31']
    assert len(trains) == 1 and trains[0].max() <= pd.Timestamp('2019-06-30 23:59:59')
    assert trains[0].max() > pd.Timestamp('2019-06-29')            # the whole train day range, not a shorter one
    assert spans and set(spans) == {('2019-07-01', '2020-03-31')}


def test_oracle_split_rewards_use_the_given_validation_span():
    import strategy_workflows.RunPlantedSignal as run
    recorded = []

    class FakeEngine:
        def evaluate_expression(self, tree):
            return 0.5, 1.0, {}

        def score_on_span(self, candidate, frame, start, end):
            recorded.append((start, end))
            return 0.25

    out = run.planted_split_rewards(FakeEngine(), FORMULA, None, CUSTOM_SEGMENTS)
    assert out['validation'] == 0.25 and recorded == [('2019-07-01', '2020-03-31')]


def make_search_args(run, tmp_path, *extra):
    import argparse
    parser = argparse.ArgumentParser()
    run.add_planted_parser(parser.add_subparsers(dest='command'))
    return parser.parse_args(['planted', 'search', '--out-dir', str(tmp_path), '--reward-mode', 'soft',
                              '--strengths', '0.0', '--seeds', '1', '--workers', '1', *extra])


def test_cli_segment_defaults_and_overrides(tmp_path):
    import strategy_workflows.RunPlantedSignal as run
    assert run.segments_from_args(make_search_args(run, tmp_path)) == Segments()
    args = make_search_args(run, tmp_path, '--train-end', '2022-06-30', '--search-end', '2023-12-31',
                            '--eval-end', '2024-12-31')
    assert run.segments_from_args(args) == Segments(train_end='2022-06-30', search_end='2023-12-31',
                                                    eval_end='2024-12-31')


def test_step_search_passes_segments_to_tasks_and_records_them(tmp_path, monkeypatch):
    import strategy_workflows.RunPlantedSignal as run
    out_dir = tmp_path / 'fresh'
    formula_file = tmp_path / 'formula.json'
    formula_file.write_text(json.dumps(formula_to_dict(FORMULA)), encoding='utf-8')
    blueprint_file = tmp_path / 'bp.json'
    blueprint_file.write_text(json.dumps([{'name': 'bp', 'macro_blueprint': 'sub(?, ts_mean(?))'}]), encoding='utf-8')
    tasks, loaded = [], []
    monkeypatch.setattr(run, 'load_base', lambda segments: loaded.append(segments) or planted_base())
    fake_row = {'reward_mode': 'soft', 'strength': 0.0, 'seed': 1, 'elapsed_s': 0.0, 'ic_search': 0.0,
                'exact': False, 'near': False, 'oos_sharpe': 0.0}
    monkeypatch.setattr(run, 'run_single', lambda task: tasks.append(task) or fake_row)
    monkeypatch.setattr(run, 'append_run', lambda path, row: None)
    monkeypatch.setattr(run, 'get_beta', lambda base, s, out, f, w, segments: 0.0)
    args = make_search_args(run, out_dir, '--search-end', '2020-03-31', '--train-end', '2019-06-30',
                            '--formula', str(formula_file), '--blueprints', str(blueprint_file))
    run.step_search(args)
    assert [t['segments'] for t in tasks] == [Segments(train_end='2019-06-30', search_end='2020-03-31')]
    assert loaded == [tasks[0]['segments']]
    stored = json.loads((out_dir / 'segments.json').read_text(encoding='utf-8'))
    assert stored == tasks[0]['segments'].to_dict()


def test_segments_json_mismatch_is_refused_unless_forced(tmp_path):
    import strategy_workflows.RunPlantedSignal as run
    run.ensure_segments(str(tmp_path), Segments())                 # missing file: written
    run.ensure_segments(str(tmp_path), Segments())                 # same split: accepted
    other = Segments(train_end='2019-06-30')
    with pytest.raises(SystemExit):
        run.ensure_segments(str(tmp_path), other)
    assert json.loads((tmp_path / 'segments.json').read_text(encoding='utf-8')) == Segments().to_dict()
    run.ensure_segments(str(tmp_path), other, force=True)
    assert Segments.from_dict(json.loads((tmp_path / 'segments.json').read_text(encoding='utf-8'))) == other


def test_calibration_key_and_beta_cache_depend_on_segments(tmp_path, monkeypatch):
    import strategy_workflows.RunPlantedSignal as run
    base = heavy_tailed_base()
    assert calibration_key(base, 0.05, FORMULA, CUSTOM_SEGMENTS) != calibration_key(base, 0.05, FORMULA)
    seen = []

    def fake(base_frame, search_end, strength, formula, workers=1):
        seen.append(search_end)
        return run.Calibration(0.03, 0.05, 0.01, [1001], 3)

    monkeypatch.setattr(run, 'calibrate_beta', fake)
    run.get_beta(base, 0.05, str(tmp_path), FORMULA, 1, CUSTOM_SEGMENTS)
    run.get_beta(base, 0.05, str(tmp_path), FORMULA, 1, Segments())
    assert seen == ['2020-03-31', '2020-06-30']


def test_load_base_reads_the_segment_range(monkeypatch):
    import strategy_workflows.RunPlantedSignal as run
    calls = []
    monkeypatch.setattr(run, 'load_data', lambda tf, start=None, end=None: calls.append((tf, start, end)))
    run.load_base(CUSTOM_SEGMENTS)
    assert calls == [('60m', '2018-08-13', '2020-09-30')]


def test_build_planted_data_splits_at_the_given_search_end():
    base = planted_base()
    data = build_planted_data(base, CUSTOM_SEGMENTS.search_end, 0.0, 1, 0.0, FORMULA)
    assert data.search.index.max() <= pd.Timestamp('2020-03-31 23:59:59')
    assert data.evaluation.index.min() >= pd.Timestamp('2020-04-01')
    assert len(data.search) + len(data.evaluation) == len(base)


def test_calibration_brackets_strength_point_two():
    base = heavy_tailed_base()
    search_end = str(base.index[50 * 24 - 1].date())
    result = calibrate_beta(base, search_end, 0.2, FORMULA, seeds=CAL_SEEDS, tolerance=0.01)
    assert result.beta > 0.0
    assert abs(result.mean_ic - 0.2) <= 0.01
    lower = calibrate_beta(base, search_end, 0.1, FORMULA, seeds=CAL_SEEDS, tolerance=0.01)
    assert 0.0 < lower.beta < result.beta
