import pytest

from strategy_workflows.GrammarSize import GrammarCounter, count_completions, count_grammar, windows_per_operator
from strategy_workflows.MCTSEngine import MCTSState, find_first_placeholder, scaled_ladders
from strategy_workflows.SemanticCompiler import SemanticCompiler
from utilities.AppConfig import MCTS_MAX_DEPTH


def compile_(text):
    return SemanticCompiler().compile_blueprint(text)


def test_five_window_reference_counts():
    # The parameter reproduces the first reference values (5 windows per rolling operator).
    five = dict(windows_per_op=5)
    assert count_completions(compile_("sub(ts_zscore(sub(pv_high, ?)), ts_zscore(sub(pv_close, ?)))"), **five) == 400
    assert count_completions(compile_("greater_than(ts_zscore(?), ts_zscore(?))"), **five) == pytest.approx(3.234e14, rel=1e-3)
    assert count_grammar(**five) == pytest.approx(1.904e41, rel=1e-3)


def test_default_window_count_is_the_engines_ladder_at_the_timeframe():
    assert windows_per_operator('60m') == len(scaled_ladders('60m')[0]) == 4
    assert windows_per_operator('10m') == len(scaled_ladders('10m')[0])
    assert GrammarCounter().windows_per_op == 4
    assert count_completions(compile_("sub(ts_zscore(sub(pv_high, ?)), ts_zscore(sub(pv_close, ?)))")) == 256
    assert count_completions(compile_("greater_than(ts_zscore(?), ts_zscore(?))")) == pytest.approx(1.04667e14, rel=1e-4)
    assert count_grammar() == pytest.approx(1.9041e41, rel=1e-3)
    assert count_grammar(max_depth=3) == pytest.approx(3.0855e20, rel=1e-3)
    assert count_grammar(max_depth=2) == pytest.approx(1.2421e10, rel=1e-3)


def test_a_blueprint_with_no_slot_has_only_its_window_choices():
    assert count_completions(compile_("ts_mean(pv_close)")) == 4
    assert count_completions(compile_("sub(pv_close, pv_open)")) == 1


def test_depth_limit_shrinks_the_count():
    shallow = count_completions(compile_("ts_mean(?)"), max_depth=2)
    deeper = count_completions(compile_("ts_mean(?)"), max_depth=4)
    assert 0 < shallow < deeper


def enumerate_terminals(state, limit=500000):
    """Every terminal state reachable by the search's own action lists (depth first)."""
    found = 0
    stack = [state]
    while stack:
        current = stack.pop()
        if current.is_terminal():
            found += 1
            assert found < limit
            continue
        actions = current.get_actions()
        assert actions, "dead end"
        stack.extend(current.apply_action(a) for a in actions)
    return found


def exhaustive_count(blueprint, max_depth):
    """(terminal states reachable by the search's action lists, expected multiplier of the template choices)."""
    root = compile_(blueprint)
    periods, windows = scaled_ladders('60m')
    state = MCTSState(root, max_depth, windows, periods)
    # The search also picks the template parameters (z-score window and threshold, or the two thresholds).
    template_choices = {'normalized_template': len(windows) * 5, 'ratio_template': 5 * 5}.get(root.name, 1)
    expected = count_completions(root, max_depth, windows_per_op=len(periods), n_constants=7) * template_choices
    return enumerate_terminals(state), expected


@pytest.mark.parametrize("blueprint, max_depth", [
    ("ts_mean(?)", 2),
    ("sub(ts_mean(?), pv_close)", 3),
    ("div(?, ts_sum(?))", 2),
    ("greater_than(ts_max(?), ts_min(?))", 2),
    ("sub(ts_mean(?), ts_mean(?))", 3),
])
def test_count_matches_exhaustive_enumeration_of_the_search_actions(blueprint, max_depth):
    enumerated, expected = exhaustive_count(blueprint, max_depth)
    assert enumerated == expected


def test_a_placed_constant_is_a_wildcard_for_the_engine_but_not_for_the_count():
    # `analyze_dimensions` lets a placed constant take any dimension, so when the constant is chosen first the
    # engine also offers `2.0 + close` (7 constants x 5 non-constant leaves, times the 25 template choices).
    # The count keeps a constant dimensionless, which is the setting of the reference values.
    enumerated, expected = exhaustive_count("add(?, ?)", 2)
    assert enumerated - expected == 7 * 5 * 25


def test_whole_grammar_is_dominated_by_the_boolean_root_and_is_monotone_in_depth():
    roots = GrammarCounter().count_roots()
    assert roots['BOOLEAN'] > 1e40 > roots['NORMALIZED'] > 1e13
    assert count_grammar(max_depth=3) < count_grammar(max_depth=4)
    assert count_grammar(roots=('NORMALIZED',)) == roots['NORMALIZED']
    assert MCTS_MAX_DEPTH == 4
