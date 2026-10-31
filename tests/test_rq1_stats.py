import math

import numpy as np
import pandas as pd
import pytest

from strategy_workflows import RunRQ1 as rq


def hypergeom_two_sided(k1, n1, k2, n2):
    """Two-sided Fisher exact p by its definition: total probability of tables no likelier than the observed one."""
    total, successes = n1 + n2, k1 + k2

    def prob(x):
        return math.comb(successes, x) * math.comb(total - successes, n1 - x) / math.comb(total, n1)
    observed = prob(k1)
    return sum(prob(x) for x in range(max(0, n1 - (total - successes)), min(n1, successes) + 1)
               if prob(x) <= observed * (1 + 1e-7))


def hypergeom_greater(k, n, base_k, base_n):
    total, successes = n + base_n, k + base_k
    return sum(math.comb(successes, x) * math.comb(total - successes, n - x) / math.comb(total, n)
               for x in range(k, min(n, successes) + 1))


def checkpoint_rows(config, ic, a, budget, near_flags, **extra):
    rows = []
    for seed, near in enumerate(near_flags, start=1):
        rows.append({'config': config, 'ic': ic, 'run_formula': '' if ic == 0 else a, 'seed': seed, 'a': a,
                     'budget': budget, 'near': bool(near), 'touched': bool(near), 'best_corr_top5': 0.5,
                     'closest_corr': 0.6, 'touch_iterations': np.nan, 'touch_evaluations': np.nan,
                     'touch_wall_s': np.nan, **extra})
    return rows


def flags(k, n):
    return [True] * k + [False] * (n - k)


def primary_frame():
    rows = []
    # (config, A, budget) -> near count out of 10 seeds, at IC 0.1
    counts = {('llm_mcts', 'A1', 50_000): 9, ('llm_mcts', 'A2', 50_000): 8, ('mcts_only', 'A1', 50_000): 3,
              ('mcts_only', 'A2', 50_000): 4,
              ('llm_mcts', 'A3', 50_000): 1, ('llm_mcts', 'A4', 50_000): 2, ('mcts_only', 'A3', 50_000): 2,
              ('mcts_only', 'A4', 50_000): 1,
              ('llm_mcts', 'A1', 100_000): 10, ('llm_mcts', 'A2', 100_000): 9, ('mcts_only', 'A1', 100_000): 6,
              ('mcts_only', 'A2', 100_000): 5,
              ('llm_mcts', 'A3', 100_000): 4, ('llm_mcts', 'A4', 100_000): 3, ('mcts_only', 'A3', 100_000): 4,
              ('mcts_only', 'A4', 100_000): 6}
    for (config, a, budget), k in counts.items():
        rows += checkpoint_rows(config, 0.1, a, budget, flags(k, 10))
        rows += checkpoint_rows(config, 0.05, a, budget, flags(10, 10))      # must not leak into the IC 0.1 test
    rows += checkpoint_rows('random', 0.1, 'A1', 50_000, flags(10, 10))      # other configs are not in the test
    return pd.DataFrame(rows)


def test_primary_test_pools_by_a_type_filters_ic_and_budget_and_uses_two_sided_fisher():
    table = rq.primary_tests(primary_frame())
    assert len(table) == 4 and list(table.columns) == rq.PRIMARY_FIELDS
    row = table[(table['budget'] == 50_000) & (table['a_type'] == 'classical')].iloc[0]
    assert (row['near_llm_mcts'], row['n_llm_mcts'], row['near_mcts_only'], row['n_mcts_only']) == (17, 20, 7, 20)
    assert row['p_two_sided'] == pytest.approx(hypergeom_two_sided(17, 20, 7, 20))
    odd = table[(table['budget'] == 100_000) & (table['a_type'] == 'odd')].iloc[0]
    assert (odd['near_llm_mcts'], odd['near_mcts_only']) == (7, 10) and odd['n_llm_mcts'] == 20
    assert odd['p_two_sided'] == pytest.approx(hypergeom_two_sided(7, 20, 10, 20))


def test_two_sided_p_is_not_the_one_sided_p_when_the_other_arm_wins():
    p = rq.fisher_two_sided(4, 20, 12, 20)
    assert p == pytest.approx(hypergeom_two_sided(4, 20, 12, 20)) and p < 0.05
    assert p == pytest.approx(2 * hypergeom_greater(12, 20, 4, 20), rel=0.05)


def test_primary_p_values_are_holm_adjusted_over_the_four_tests():
    table = rq.primary_tests(primary_frame())
    raw = list(table['p_two_sided'])
    order = np.argsort(raw)
    expected = [None] * 4
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (4 - rank) * raw[i]))
        expected[i] = running
    assert list(table['p_holm']) == pytest.approx(expected)
    assert all(adj >= p for adj, p in zip(table['p_holm'], raw)) and table['p_holm'].max() <= 1.0


def test_primary_test_with_an_empty_arm_is_nan_and_left_out_of_the_family():
    frame = primary_frame()
    frame = frame[~((frame['config'] == 'mcts_only') & (frame['budget'] == 50_000))]
    table = rq.primary_tests(frame)
    assert table[table['budget'] == 50_000]['p_two_sided'].isna().all() and table[table['budget'] == 50_000]['p_holm'].isna().all()
    done = table[table['budget'] == 100_000]
    low, high = sorted(done['p_two_sided'])
    assert max(done['p_holm']) == pytest.approx(max(min(1.0, 2 * low), min(1.0, high)))


def test_a_rerun_of_a_cell_replaces_its_old_row_in_the_test():
    frame = primary_frame()
    again = pd.DataFrame(checkpoint_rows('llm_mcts', 0.1, 'A1', 50_000, flags(0, 10)))
    table = rq.primary_tests(pd.concat([frame, again]))
    row = table[(table['budget'] == 50_000) & (table['a_type'] == 'classical')].iloc[0]
    assert row['near_llm_mcts'] == 8                          # A1 now 0 of 10, A2 still 8


# --- rates with Wilson intervals ------------------------------------------------

def test_summary_has_wilson_intervals_and_no_p_value_columns():
    frame = pd.DataFrame(checkpoint_rows('random', 0.1, 'A1', 50_000, flags(5, 10)))
    frame['touched'] = flags(2, 10)                             # touched differs from near, so a mix-up shows
    row = rq.summarize_checkpoints(frame).iloc[0]
    assert (row['touched_low'], row['touched_high']) == pytest.approx((0.0567, 0.5099), abs=1e-3)
    assert row['near_rate'] == pytest.approx(0.5)
    assert row['near_low'] == pytest.approx(0.2366, abs=1e-3) and row['near_high'] == pytest.approx(0.7634, abs=1e-3)
    assert not any('p_' in c or c.startswith('p') and c.endswith('value') for c in rq.summarize_checkpoints(frame).columns)
    zero = rq.summarize_checkpoints(pd.DataFrame(checkpoint_rows('random', 0.1, 'A1', 50_000, flags(0, 10)))).iloc[0]
    assert zero['near_low'] == 0.0 and zero['near_high'] == pytest.approx(0.2775, abs=1e-3)


# --- RQ2 detection threshold ----------------------------------------------------

def detection_frame(counts, a='A1', budget=100_000, config='llm_mcts', n=10):
    rows = []
    for ic, k in counts.items():
        rows += checkpoint_rows(config, ic, a, budget, flags(k, n))
    return rows


def test_detection_threshold_is_the_lowest_ic_with_one_sided_fisher_p_below_0_05():
    rows = detection_frame({0.0: 1, 0.05: 3, 0.1: 8}) + detection_frame({0.0: 1, 0.05: 6, 0.1: 9}, a='A2') \
        + detection_frame({0.0: 2, 0.05: 3, 0.1: 4}, a='A3')
    rows += detection_frame({0.0: 0, 0.05: 10, 0.1: 10}, config='random')        # another config is ignored
    rows += detection_frame({0.0: 0, 0.05: 10, 0.1: 10}, budget=50_000)           # another budget is ignored
    table = rq.detection_thresholds(pd.DataFrame(rows)).set_index('a')
    assert hypergeom_greater(3, 10, 1, 10) > 0.05 > hypergeom_greater(8, 10, 1, 10)
    assert table.loc['A1', 'threshold_ic'] == 0.1 and table.loc['A1', 'p_fisher'] == pytest.approx(hypergeom_greater(8, 10, 1, 10))
    assert hypergeom_greater(6, 10, 1, 10) < 0.05
    assert table.loc['A2', 'threshold_ic'] == 0.05                                # the lowest passing level wins
    assert np.isnan(table.loc['A3', 'threshold_ic']) and np.isnan(table.loc['A3', 'p_fisher'])
    assert table.loc['A1', 'rates'] == 'IC 0: 1/10; IC 0.05: 3/10; IC 0.1: 8/10'


def test_detection_needs_an_ic_zero_row_and_counts_ic_02_when_present():
    none = rq.detection_thresholds(pd.DataFrame(detection_frame({0.05: 9, 0.1: 10})))
    assert np.isnan(none.iloc[0]['threshold_ic'])
    extra = rq.detection_thresholds(pd.DataFrame(detection_frame({0.0: 0, 0.05: 1, 0.1: 1, 0.2: 9})))
    assert extra.iloc[0]['threshold_ic'] == 0.2


# --- first touch ------------------------------------------------------------------

def test_first_touch_medians_use_the_last_budget_and_only_runs_that_touched():
    rows = []
    for budget, touch in ((50_000, [100, 900, np.nan]), (100_000, [100, 900, np.nan])):
        for seed, it in enumerate(touch, start=1):
            rows.append({'config': 'random', 'ic': 0.1, 'run_formula': 'A1', 'seed': seed, 'a': 'A1', 'budget': budget,
                         'near': False, 'touched': not np.isnan(it), 'touch_iterations': it,
                         'touch_evaluations': it * 0.8, 'touch_wall_s': it / 100, 'best_corr_top5': 0, 'closest_corr': 0})
    table = rq.first_touch_table(pd.DataFrame(rows))
    row = table.iloc[0]
    assert len(table) == 1 and row['budget'] == 100_000
    assert (row['n_runs'], row['n_touched']) == (3, 2)
    assert row['median_iterations'] == pytest.approx(500) and row['median_evaluations'] == pytest.approx(400)
    assert row['median_wall_s'] == pytest.approx(5.0)


def test_summary_step_writes_all_four_tables(tmp_path, capsys):
    primary_frame().assign(run_formula='A1').to_csv(tmp_path / 'checkpoints.csv', index=False)
    rq.step_summary(type('A', (), {'out_dir': str(tmp_path)})())
    for name in ('summary.csv', 'primary_tests.csv', 'detection_thresholds.csv', 'first_touch.csv'):
        assert (tmp_path / name).exists()
    assert len(pd.read_csv(tmp_path / 'primary_tests.csv')) == 4
