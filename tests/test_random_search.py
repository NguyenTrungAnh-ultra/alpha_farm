import random
from collections import Counter

import numpy as np
import pandas as pd
import pytest

from strategy_workflows.MCTSDimensions import OPERATOR_REGISTRY, analyze_dimensions
from strategy_workflows.MCTSEngine import MCTSEngine, describe_candidate, scaled_ladders
from strategy_workflows import RandomSearch as rs

PERIODS, WINDOWS = scaled_ladders('60m')


@pytest.fixture
def frame():
    rng = np.random.default_rng(4)
    index = pd.date_range('2024-01-01', periods=600, freq='h', name='Datetime')
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.002, len(index)))
    return pd.DataFrame({
        'Open': close * rng.uniform(0.999, 1.001, len(index)), 'High': close * rng.uniform(1.0, 1.003, len(index)),
        'Low': close * rng.uniform(0.997, 1.0, len(index)), 'Close': close,
        'Volume': rng.uniform(1000, 5000, len(index)),
    }, index=index)


def tree_depth(node, depth=0):
    return max([depth] + [tree_depth(c, depth + 1) for c in node.children])


def operator_levels(node):
    below = [operator_levels(c) for c in node.children]
    return (1 if node.name in OPERATOR_REGISTRY else 0) + max(below, default=0)


def test_depth_shares_are_exact_for_the_budget_and_balanced_in_every_prefix():
    total = 1000
    cells = Counter(rs.cell_for_index(i) for i in range(total))
    assert set(cells) == set(rs.CELLS) and len(rs.CELLS) == 8
    assert all(count == total // 8 for count in cells.values())
    by_depth = Counter(depth for depth, _ in (rs.cell_for_index(i) for i in range(total)))
    assert by_depth == {1: 250, 2: 250, 3: 250, 4: 250}
    by_method = Counter(method for _, method in (rs.cell_for_index(i) for i in range(total)))
    assert by_method == {'full': 500, 'grow': 500}
    # any prefix is near-equal, so an early checkpoint is not only shallow (or only deep) trees
    prefix = Counter(depth for depth, _ in (rs.cell_for_index(i) for i in range(1250)))
    assert max(prefix.values()) - min(prefix.values()) <= 2


def test_random_search_draws_the_planned_depths(frame):
    engine = MCTSEngine(timeframe='60m', data=frame, seed=1, reward_mode='sharpe', global_position_matrix=None)
    stats = rs.random_search(engine, 80, 40)
    assert stats['samples'] == 80 and stats['per_depth'] == {1: 20, 2: 20, 3: 20, 4: 20}


@pytest.mark.parametrize("template", rs.TEMPLATES)
@pytest.mark.parametrize("depth", rs.DEPTHS)
@pytest.mark.parametrize("method", rs.METHODS)
def test_generated_trees_are_complete_dimension_valid_and_within_the_depth_limit(template, depth, method):
    rng = random.Random(f"{template}{depth}{method}")
    for _ in range(25):
        tree = rs.generate_formula(rng, template, depth, method, WINDOWS, PERIODS)
        assert analyze_dimensions(tree, depth + (1 if template == 'BOOLEAN' else 0)).error is None
        desc = describe_candidate(tree)              # renders: every window and parameter is chosen
        assert desc['template'] == template
        # numeric roots sit under a template node (depth 0): depth D allows D - 1 operator levels
        if template == 'BOOLEAN':
            assert operator_levels(tree) <= depth + 1
        else:
            assert operator_levels(tree.children[0]) <= depth - 1
        assert tree_depth(tree) <= depth + (1 if template == 'BOOLEAN' else 0)


def test_choices_come_from_the_ladders_the_search_uses():
    rng = random.Random(7)
    seen_periods, seen_z = set(), set()
    for _ in range(300):
        tree = rs.generate_formula(rng, 'NORMALIZED', 4, 'grow', WINDOWS, PERIODS)
        stack = [tree]
        while stack:
            node = stack.pop()
            stack.extend(node.children)
            if node.window is not None:
                seen_periods.add(node.window)
            if node.name == 'window':
                seen_z.add(node.value)
    assert seen_periods == set(PERIODS) and seen_z == set(WINDOWS)


def test_full_trees_are_deeper_than_grown_ones_on_average():
    rng = random.Random(11)
    full = np.mean([operator_levels(rs.generate_formula(rng, 'NORMALIZED', 4, 'full', WINDOWS, PERIODS))
                    for _ in range(80)])
    grow = np.mean([operator_levels(rs.generate_formula(rng, 'NORMALIZED', 4, 'grow', WINDOWS, PERIODS))
                    for _ in range(80)])
    assert full > grow
    assert full == 3        # depth 4 under a template node = 3 operator levels, and a full tree uses all of them


def test_a_depth_one_numeric_tree_is_a_single_leaf():
    rng = random.Random(2)
    for _ in range(20):
        tree = rs.generate_formula(rng, 'NORMALIZED', 1, 'full', WINDOWS, PERIODS)
        assert rs.count_operators(tree) == 0


def test_same_seed_gives_the_same_formulas_and_leaderboard(frame):
    def run(seed):
        engine = MCTSEngine(timeframe='60m', data=frame, seed=seed, reward_mode='sharpe', global_position_matrix=None)
        rs.random_search(engine, 120, 40)
        return [(c['expr'], c['reward']) for c in engine.leaderboard], engine.evaluation_count
    assert run(3) == run(3)
    assert run(3) != run(4)


def test_duplicates_are_skipped_but_count_against_the_budget(frame):
    engine = MCTSEngine(timeframe='60m', data=frame, seed=1, reward_mode='sharpe', global_position_matrix=None)
    calls = []
    original = engine.evaluate_expression

    def counting(tree):
        calls.append(describe_candidate(tree)['cache_key'])
        return original(tree)

    engine.evaluate_expression = counting
    stats = rs.random_search(engine, 200, 50)
    assert stats['samples'] == 200 and stats['duplicates'] > 0
    assert len(calls) == len(set(calls)) == 200 - stats['duplicates']


def test_on_chunk_reports_the_samples_since_the_last_call(frame):
    engine = MCTSEngine(timeframe='60m', data=frame, seed=1, reward_mode='sharpe', global_position_matrix=None)
    reported = []
    rs.random_search(engine, 105, 40, reported.append)
    assert reported == [40, 40, 25]


def test_random_search_fills_the_leaderboard_the_selection_reads(frame):
    from strategy_workflows.PlantedSignal import Segments, distinct_expressions
    from strategy_workflows.RunPlantedSignal import rank_leaderboard
    engine = MCTSEngine(timeframe='60m', data=frame.iloc[:400], seed=1, reward_mode='sharpe',
                        global_position_matrix=None)
    rs.random_search(engine, 300, 100)
    assert len(engine.leaderboard) > 5
    segments = Segments(search_start=str(frame.index[0].date()), train_end=str(frame.index[399].date()),
                        search_end=str(frame.index[550].date()), eval_end=str(frame.index[-1].date()))
    picked = rank_leaderboard(engine, frame.loc[:segments.search_end], segments)
    assert 0 < len(picked['chosen']) <= 5
    assert len(distinct_expressions(engine.leaderboard)) >= len(picked['chosen'])
