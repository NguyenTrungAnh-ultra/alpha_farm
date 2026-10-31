import json
import random

import numpy as np
import pandas as pd
import pytest

from strategy_workflows import PlantedFormulas as pf
from strategy_workflows.MCTSEngine import MCTSEngine, scaled_ladders
from strategy_workflows.PlantedSignal import (
    PlantedFormula, assert_in_search_space, formula_from_dict, formula_to_dict, plant_signal, realized_ic, spearman_abs,
)
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler


@pytest.fixture(scope='module')
def frame():
    rng = np.random.default_rng(21)
    index = pd.date_range('2023-01-02', periods=900, freq='h', name='Datetime')
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.003, len(index)))
    return pd.DataFrame({
        'Open': close * rng.uniform(0.998, 1.002, len(index)), 'High': close * rng.uniform(1.0, 1.01, len(index)),
        'Low': close * rng.uniform(0.99, 1.0, len(index)), 'Close': close,
        'Volume': rng.uniform(1000, 5000, len(index)),
    }, index=index)


@pytest.fixture(scope='module')
def crowd(frame):
    return pf.CrowdingSample(frame, 400)


@pytest.fixture(scope='module')
def stationary_frame():
    """Prices that mean-revert around 1000: every price-level series is stationary and they all correlate."""
    rng = np.random.default_rng(5)
    n = 900
    level = np.zeros(n)
    for i in range(1, n):
        level[i] = 0.9 * level[i - 1] + rng.normal(0.0, 5.0)
    close = 1000.0 + level
    index = pd.date_range('2023-01-02', periods=n, freq='h', name='Datetime')
    return pd.DataFrame({
        'Open': close + rng.normal(0, 1, n), 'High': close + rng.uniform(0, 3, n), 'Low': close - rng.uniform(0, 3, n),
        'Close': close, 'Volume': rng.uniform(1000, 5000, n)}, index=index)


def node(name, window=None, children=(), value=None):
    return ASTNode(name=name, children=list(children), window=window, value=value)


def formula_of(tree, sign=1.0, z=10):
    return PlantedFormula(tree=tree, z_window=z, sign=sign)


# --- A1 / A2 ----------------------------------------------------------------

def test_a1_and_a2_are_the_classical_formulas_with_the_chosen_signs():
    a = pf.classical_formulas()
    assert a['A1'].expr == 'ts_corr(close, volume, 10)' and a['A1'].sign == 1.0 and a['A1'].z_window == 10
    assert a['A2'].expr == 'ts_mean((close - open_), 10)' and a['A2'].sign == 1.0
    engine = MCTSEngine(timeframe='60m', data=pd.DataFrame(
        {'Open': [1.0], 'High': [1.0], 'Low': [1.0], 'Close': [1.0], 'Volume': [1.0]},
        index=pd.date_range('2024-01-01', periods=1)), reward_mode='sharpe', global_position_matrix=None)
    for formula in a.values():
        assert_in_search_space(engine, formula)
        assert pf.fits_depth_limit(formula)


def test_negative_sign_mirrors_the_signal_and_plants_a_reverting_drive(frame):
    plus = formula_of(node('ts_zscore', 10, [node('pv_close')]), 1.0)
    minus = formula_of(node('ts_zscore', 10, [node('pv_close')]), -1.0)
    both = pd.concat([plus.signal_series(frame), minus.signal_series(frame)], axis=1).dropna()
    assert np.allclose(both.iloc[:, 0], -both.iloc[:, 1])

    eps = np.random.default_rng(0).normal(0.0, 0.003, 3000)
    eps[0] = 0.0
    sigma = np.full(len(eps), 0.003)
    results = {}
    for name, formula in (('plus', plus), ('minus', minus)):
        results[name] = plant_signal(eps, sigma, 1000.0, 0.5, formula.signal_last, formula.lookback)
    # the signed signal always predicts the next return positively ...
    for result in results.values():
        assert realized_ic(pd.Series(result.signal), pd.Series(result.closes)) > 0.05
    # ... and the raw z-score of the price is anti-correlated with it for the negative sign (mean reversion)
    raw = pd.Series(results['minus'].signal) * -1.0
    assert realized_ic(raw, pd.Series(results['minus'].closes)) < -0.05


def test_sign_is_stored_only_when_negative_and_survives_a_roundtrip_with_constants():
    tree = node('mult', None, [node('pv_close'), node('Constant', value=0.5)])
    for sign in (1.0, -1.0):
        formula = formula_of(tree, sign)
        data = formula_to_dict(formula)
        assert ('sign' in data) == (sign == -1.0)
        back = formula_from_dict(json.loads(json.dumps(data)))
        assert back.expr == formula.expr == '(close * 0.5)' and back.sign == sign


def test_calibration_key_changes_with_the_sign_but_not_for_the_old_positive_case():
    from strategy_workflows.RunPlantedSignal import calibration_key
    frame_ = pd.DataFrame({'Close': [1.0, 2.0]}, index=pd.date_range('2024-01-01', periods=2))
    tree = node('ts_zscore', 10, [node('pv_close')])
    positive, negative = formula_of(tree, 1.0), formula_of(tree, -1.0)
    assert 'sign' not in calibration_key(frame_, 0.1, positive)
    assert calibration_key(frame_, 0.1, negative) != calibration_key(frame_, 0.1, positive)


# --- A3 / A4 ----------------------------------------------------------------

def test_random_formulas_have_exactly_the_requested_operator_count(frame):
    for n in (1, 2):
        rng = random.Random(n)
        seen = 0
        for draw in range(200):
            tree = pf.draw_random_formula(rng, n, draw)
            if tree is not None:
                assert pf.count_operators(tree) == n
                seen += 1
        assert seen > 10


def passing_checks(formulas, frame_, crowd_):
    return {n: {'adf_p': 0.0, 'crowding_share': 0.0} for n in formulas}


def test_a3_and_a4_are_deterministic_and_have_one_and_two_operators(frame, crowd, monkeypatch):
    monkeypatch.setattr(pf, 'check_classical_formulas', passing_checks)
    first = pf.select_rq1_formulas(frame, crowd=crowd)
    second = pf.select_rq1_formulas(frame, crowd=crowd)
    assert {k: v[0].expr for k, v in first.items()} == {k: v[0].expr for k, v in second.items()}
    assert pf.count_operators(first['A3'][0].tree) == 1 and pf.count_operators(first['A4'][0].tree) == 2
    assert first['A3'][1]['seed'] == 1 and first['A4'][1]['seed'] == 2
    other_seed, _ = pf.select_random_formula('A3', 1, 99, frame, pf.classical_formulas(), crowd=crowd)
    assert other_seed.expr != first['A3'][0].expr


def test_one_crowding_sample_serves_all_four_formulas(frame, monkeypatch):
    built = []
    real_init = pf.CrowdingSample.__init__

    def counting_init(self, *args, **kwargs):
        built.append(1)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(pf.CrowdingSample, '__init__', counting_init)
    monkeypatch.setattr(pf, 'CROWDING_SAMPLES', 200)
    monkeypatch.setattr(pf, 'check_classical_formulas', passing_checks)
    selected = pf.select_rq1_formulas(frame)
    assert len(built) == 1
    assert {info['crowding_drawn'] for _, info in selected.values()} == {200}


def test_selected_random_formulas_pass_all_rules_and_record_their_numbers(frame, crowd):
    references = pf.classical_formulas()
    for name, n_operators, seed in (('A3', 1, 1), ('A4', 2, 2)):
        formula, info = pf.select_random_formula(name, n_operators, seed, frame, references, crowd=crowd)
        assert pf.rejection_reason(formula, frame, references, crowd) is None
        assert not pf.is_constant_on(formula, frame) and pf.has_rolling_operator(formula.tree)
        assert info['adf_p'] < pf.ADF_ALPHA and info['crowding_share'] < pf.CROWDING_LIMIT
        assert info['candidates'] == len(info['rejected']) + 1 and info['draws'] >= info['candidates']
        assert all('reason' in item and 'expression' in item for item in info['rejected'])


def test_adf_rejects_a_random_walk_level_and_accepts_a_zscore(frame):
    level = pf.adf_p_value(formula_of(node('pv_close')).alpha_series(frame))
    zscore = pf.adf_p_value(formula_of(node('ts_zscore', 10, [node('pv_close')])).alpha_series(frame))
    assert level >= pf.ADF_ALPHA and not pf.is_stationary(level)
    assert zscore < pf.ADF_ALPHA and pf.is_stationary(zscore)
    assert not pf.is_stationary(float('nan'))
    reason = pf.rejection_reason(formula_of(node('ts_sum', 5, [node('pv_close')])), frame, {})
    assert reason.startswith('not stationary')


def test_a_crowded_price_level_formula_is_rejected_and_an_unusual_one_is_not(stationary_frame):
    crowd = pf.CrowdingSample(stationary_frame, 600)
    level = formula_of(node('ts_mean', 3, [node('pv_high')]))        # stationary here, correlates with every price level
    assert pf.is_stationary(pf.adf_p_value(level.alpha_series(stationary_frame)))
    assert crowd.share(level.alpha_series(stationary_frame)) >= pf.CROWDING_LIMIT
    assert pf.rejection_reason(level, stationary_frame, {}, crowd).startswith('crowded')
    unusual = formula_of(node('ts_corr', 5, [node('pv_volume'), node('pv_low')]))
    assert pf.rejection_reason(unusual, stationary_frame, {}, crowd) is None


def test_crowding_share_counts_valid_formulas_only(frame):
    crowd = pf.CrowdingSample(frame, 300)
    assert 0 < crowd.n_valid < crowd.n_drawn
    target = formula_of(node('ts_zscore', 10, [node('pv_close')])).alpha_series(frame)
    hits = sum(spearman_abs(pd.Series(row, index=frame.index), target) >= pf.NEAR_CORRELATION for row in crowd.values)
    assert hits > 0
    assert crowd.share(target) == pytest.approx(hits / crowd.n_valid, abs=0.005)


def test_crowding_sample_is_deterministic(frame):
    first, second = pf.CrowdingSample(frame, 150), pf.CrowdingSample(frame, 150)
    assert first.n_valid == second.n_valid and np.array_equal(first.values, second.values, equal_nan=True)


def test_a_formula_without_a_rolling_operator_is_rejected(stationary_frame):
    plain = formula_of(node('add', None, [node('pv_high'), node('pv_low')]))
    assert not pf.has_rolling_operator(plain.tree)
    assert pf.rejection_reason(plain, stationary_frame, {}) == 'no rolling ts_ operator'
    mixed = formula_of(node('sub', None, [node('pv_high'), node('ts_mean', 3, [node('pv_low')])]))
    assert pf.has_rolling_operator(mixed.tree)


def test_a_formula_with_the_tree_shape_of_a1_or_a2_is_rejected_and_other_shapes_are_not(stationary_frame):
    references = pf.classical_formulas()
    like_a1 = formula_of(node('ts_corr', 3, [node('pv_open'), node('pv_low')]))
    like_a2 = formula_of(node('ts_mean', 7, [node('sub', None, [node('pv_high'), node('pv_low')])]))
    for formula in (like_a1, like_a2):
        assert pf.rejection_reason(formula, stationary_frame, references) == 'same tree shape as A1 or A2'
    other = formula_of(node('ts_mean', 3, [node('pv_volume')]))
    assert pf.rejection_reason(other, stationary_frame, references) != 'same tree shape as A1 or A2'


class FixedShareCrowd:
    n_drawn, n_valid = 10, 10

    def __init__(self, share):
        self._share = share

    def share(self, alpha):
        return self._share


def test_a1_or_a2_failing_stationarity_or_crowding_stops_the_selection(frame, monkeypatch):
    formulas = pf.classical_formulas()
    with pytest.raises(pf.ClassicalCheckFailed, match='crowded'):
        pf.check_classical_formulas(formulas, frame, FixedShareCrowd(0.05))
    assert set(pf.check_classical_formulas(formulas, frame, FixedShareCrowd(0.0))) == {'A1', 'A2'}
    with pytest.raises(pf.ClassicalCheckFailed, match='A1 is crowded'):
        pf.select_rq1_formulas(frame, crowd=FixedShareCrowd(0.5))
    monkeypatch.setattr(pf, 'adf_p_value', lambda alpha: 0.4)
    with pytest.raises(pf.ClassicalCheckFailed, match='not stationary'):
        pf.select_rq1_formulas(frame, crowd=FixedShareCrowd(0.0))


def test_constant_formulas_are_rejected():
    flat = pd.DataFrame({'Open': 1.0, 'High': 1.0, 'Low': 1.0, 'Close': 1.0, 'Volume': 1.0},
                        index=pd.date_range('2024-01-01', periods=300, freq='h'))
    series = np.cumsum(np.random.default_rng(1).normal(size=300))
    moving = flat.assign(Close=1000 + series, Open=1000 + series, High=1001 + series, Low=999 + series)
    spread = formula_of(node('sub', None, [node('pv_close'), node('pv_close')]))          # close - close
    only_constants = formula_of(node('div', None, [node('Constant', value=0.1), node('Constant', value=0.2)]))
    assert pf.is_constant_on(spread, moving) and pf.is_constant_on(only_constants, moving)
    assert pf.is_constant_on(formula_of(node('pv_volume')), flat)                           # flat volume
    assert not pf.is_constant_on(formula_of(node('pv_close')), moving)
    assert pf.rejection_reason(spread, moving, {}) == 'constant on the search segment'


def test_formulas_correlated_with_a1_or_a2_are_rejected(frame):
    references = pf.classical_formulas()
    # ts_corr(close, volume, 9) tracks ts_corr(close, volume, 10); the mean of (close - open) over 9 bars tracks A2
    like_a1 = formula_of(node('ts_corr', 9, [node('pv_close'), node('pv_volume')]))
    like_a2 = formula_of(node('ts_mean', 9, [node('sub', None, [node('pv_close'), node('pv_open')])]))
    assert spearman_abs(like_a1.alpha_series(frame), references['A1'].alpha_series(frame)) >= 0.7
    assert spearman_abs(like_a2.alpha_series(frame), references['A2'].alpha_series(frame)) >= 0.7
    assert 'A1' in pf.rejection_reason(like_a1, frame, references)
    assert 'A2' in pf.rejection_reason(like_a2, frame, references)
    unrelated = formula_of(node('ts_mean', 5, [node('pv_volume')]))
    assert spearman_abs(unrelated.alpha_series(frame), references['A1'].alpha_series(frame)) < 0.7
    assert pf.rejection_reason(unrelated, frame, references) is None


def test_the_next_candidate_of_the_same_seed_is_taken_after_a_rejection(frame, crowd, monkeypatch):
    first, info = pf.select_random_formula('A3', 1, 1, frame, pf.classical_formulas(), crowd=crowd)
    # Force the first acceptable candidate to be rejected: the next acceptable draw of the same stream follows.
    real = pf.check_formula
    state = {'seen': 0}

    def reject_first(formula, *args, **kwargs):
        reason, stats = real(formula, *args, **kwargs)
        if reason is None:
            state['seen'] += 1
            return ('forced' if state['seen'] == 1 else None), stats
        return reason, stats

    monkeypatch.setattr(pf, 'check_formula', reject_first)
    second, second_info = pf.select_random_formula('A3', 1, 1, frame, pf.classical_formulas(), crowd=crowd)
    assert second.expr != first.expr
    assert second_info['draws'] > info['draws']
    assert any(item['expression'] == first.expr and item['reason'] == 'forced' for item in second_info['rejected'])


def test_formulas_file_roundtrip(frame, crowd, monkeypatch):
    monkeypatch.setattr(pf, 'check_classical_formulas', passing_checks)
    selected = pf.select_rq1_formulas(frame, crowd=crowd)
    data = json.loads(json.dumps(pf.formulas_to_dict(selected)))
    back = pf.formulas_from_dict(data)
    assert {k: v.expr for k, v in back.items()} == {k: v[0].expr for k, v in selected.items()}
    assert back['A1'].sign == 1.0 and data['A3']['selection']['kind'] == 'random'


# --- region of the blueprint set -------------------------------------------

def compile_(text):
    return SemanticCompiler().compile_blueprint(text)


def test_coverage_names_expressing_blueprints_and_the_smallest_by_completions():
    a2 = pf.classical_formulas()['A2']        # ts_mean(sub(pv_close, pv_open), 10)
    blueprints = [
        {'name': 'wide', 'macro_blueprint': 'ts_mean(?)'},
        {'name': 'narrow', 'macro_blueprint': 'ts_mean(sub(?, pv_open))'},
        {'name': 'spelled_out', 'macro_blueprint': 'ts_mean(sub(pv_close, pv_open))'},
        {'name': 'other_root', 'macro_blueprint': 'greater_than(ts_mean(?), ts_max(?))'},
        {'name': 'wrong_op', 'macro_blueprint': 'ts_sum(?)'},
    ]
    report = pf.coverage_report(blueprints, a2)
    assert report['expressing'] == ['wide', 'narrow', 'spelled_out']
    assert report['verbatim'] == ['spelled_out']
    assert report['in_region'] and report['fits_depth_limit']
    assert report['completions']['spelled_out'] == 4                       # only the window is left to find
    assert report['smallest'] == {'name': 'spelled_out', 'completions': 4}
    assert report['completions']['narrow'] < report['completions']['wide']


def test_coverage_of_a_formula_outside_the_region():
    a1 = pf.classical_formulas()['A1']
    report = pf.coverage_report([{'name': 'x', 'macro_blueprint': 'sub(ts_mean(?), ts_mean(?))'},
                                 {'name': 'y', 'macro_blueprint': 'greater_than(?, ?)'}], a1)
    assert report['in_region'] is False and report['expressing'] == [] and report['smallest'] is None


def test_a_formula_deeper_than_the_limit_does_not_fit():
    deep = node('ts_mean', 2, [node('ts_sum', 2, [node('ts_max', 2, [node('ts_min', 2, [node('pv_close')])])])])
    assert not pf.fits_depth_limit(formula_of(deep))
    shallow = node('ts_mean', 2, [node('ts_sum', 2, [node('ts_max', 2, [node('pv_close')])])])
    assert pf.fits_depth_limit(formula_of(shallow))
    periods, windows = scaled_ladders('60m')
    assert 10 in periods and 10 in windows
