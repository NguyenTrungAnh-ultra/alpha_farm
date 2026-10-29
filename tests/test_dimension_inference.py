import random
import zlib

import pytest

from strategy_workflows.MCTSDimensions import (
    Dimension, analyze_dimensions, result_dim,
)
from strategy_workflows.MCTSEngine import MCTSState
from strategy_workflows.SemanticCompiler import SemanticCompiler, SemanticCompilerError

C, V, R, B = Dimension.CURRENCY, Dimension.VOLUME, Dimension.RATIO, Dimension.BOOLEAN


def slots(node):
    """All `?` nodes of a tree, depth first, left to right."""
    found = [node] if node.name == "?" else []
    for child in node.children:
        found += slots(child)
    return found


def slot_dims(blueprint, max_depth=None):
    root = SemanticCompiler().compile_blueprint(blueprint)
    analysis = analyze_dimensions(root, max_depth)
    return [analysis.slot_dims[id(s)] for s in slots(root)]


# ─── Propagation rules ───────────────────────────────────────────────────

@pytest.mark.parametrize("op", ["ts_mean", "ts_sum", "ts_max", "ts_min"])
@pytest.mark.parametrize("dim", [C, V, R])
def test_rolling_aggregates_keep_the_input_dimension(op, dim):
    assert result_dim(op, (dim,)) == dim


@pytest.mark.parametrize("op", ["ts_argmax", "ts_argmin", "ts_rank", "ts_zscore"])
def test_rank_like_operators_are_dimensionless(op):
    assert {result_dim(op, (d,)) for d in (C, V, R)} == {R}


def test_ts_corr_takes_any_two_series_and_returns_ratio():
    assert result_dim("ts_corr", (C, V)) == R


def test_add_sub_need_equal_dimensions():
    for op in ("add", "sub"):
        assert result_dim(op, (C, C)) == C
        assert result_dim(op, (V, V)) == V
        assert result_dim(op, (C, V)) is None
        assert result_dim(op, (C, R)) is None


def test_mult_needs_a_ratio_side():
    assert result_dim("mult", (R, R)) == R
    assert result_dim("mult", (R, C)) == C
    assert result_dim("mult", (V, R)) == V
    assert result_dim("mult", (C, V)) is None
    assert result_dim("mult", (C, C)) is None


def test_div_of_equal_dimensions_is_ratio_and_ratio_divisor_keeps_numerator():
    assert result_dim("div", (C, C)) == R
    assert result_dim("div", (C, R)) == C
    assert result_dim("div", (R, C)) is None
    assert result_dim("div", (C, V)) is None


def test_comparison_needs_equal_dimensions():
    assert result_dim("greater_than", (C, C)) == B
    assert result_dim("less_than", (V, R)) is None


def test_boolean_and_numeric_inputs_do_not_mix():
    assert result_dim("and_", (B, B)) == B
    assert result_dim("and_", (C, B)) is None
    assert result_dim("ts_mean", (B,)) is None
    assert result_dim("greater_than", (B, B)) is None


# ─── Compiler: dimensions are seen through nested operators ──────────────

def test_direct_mixing_is_rejected():
    with pytest.raises(SemanticCompilerError, match="Dimensional Bleeding"):
        SemanticCompiler().compile_blueprint("greater_than(pv_close, pv_volume)")


@pytest.mark.parametrize("blueprint", [
    "sub(ts_mean(pv_close), ts_mean(pv_volume))",
    "sub(pv_close, ts_sum(pv_volume))",
    "sub(pv_close, mult(pv_high, pv_volume))",
    "sub(pv_close, ts_argmin(pv_high))",
    "greater_than(ts_sum(pv_volume), ts_mean(pv_open))",
])
def test_nested_mixed_dimensions_are_rejected(blueprint):
    with pytest.raises(SemanticCompilerError):
        SemanticCompiler().compile_blueprint(blueprint)


@pytest.mark.parametrize("blueprint", [
    "sub(ts_mean(pv_close), ts_mean(pv_open))",
    "greater_than(ts_sum(pv_volume), ts_mean(pv_volume))",
    "sub(pv_close, mult(pv_high, ts_zscore(pv_volume)))",
    "sub(ts_zscore(pv_close), ts_argmin(pv_high))",
    "div(ts_mean(pv_close), ts_max(pv_high))",
])
def test_nested_consistent_dimensions_are_accepted(blueprint):
    SemanticCompiler().compile_blueprint(blueprint)


# ─── Slot inference ──────────────────────────────────────────────────────

def test_slot_next_to_a_field_takes_the_field_dimension():
    assert slot_dims("sub(pv_close, ts_mean(?))") == [frozenset({C})]
    assert slot_dims("greater_than(ts_sum(pv_volume), ts_mean(?))") == [frozenset({V})]


def test_free_slots_may_take_any_numeric_dimension():
    assert slot_dims("sub(ts_mean(?), ts_mean(?))") == [frozenset({C, V, R})] * 2


def test_mult_slot_next_to_a_field_must_be_ratio():
    assert slot_dims("mult(pv_close, ?)") == [frozenset({R})]


def test_div_root_is_a_ratio_so_its_slot_matches_the_numerator():
    assert slot_dims("div(pv_close, ?)") == [frozenset({C})]


def test_slot_under_a_comparison_is_constrained_through_nested_operators():
    assert slot_dims("greater_than(ts_sum(pv_volume), ts_mean(add(?, ?)))") == [frozenset({V})] * 2


def test_dead_blueprint_is_rejected():
    # `?` must be CURRENCY to add to pv_open, but the right side must then be VOLUME.
    with pytest.raises(SemanticCompilerError, match="Dimensional Bleeding in greater_than"):
        SemanticCompiler().compile_blueprint("greater_than(ts_sum(pv_volume), ts_mean(add(?, pv_open)))")


def test_dead_blueprint_message_keeps_the_self_correction_prefix():
    from strategy_workflows.GenerateStrategies import validate_idea
    idea = {
        "name": "dead", "timeframe": "10m", "family": "x", "description": "x",
        "macro_blueprint": "greater_than(ts_sum(pv_volume), ts_mean(add(?, pv_open)))",
    }
    with pytest.raises(ValueError, match="Macro-Blueprint Semantic Error"):
        validate_idea(idea)


def test_depth_limit_makes_a_ratio_slot_under_a_rolling_operator_unreachable():
    # The slot in ts_mean(?) must be RATIO (beside ts_zscore), and a RATIO under a rolling
    # operator needs an operator of its own: one more level than depth 3 leaves.
    root = SemanticCompiler().compile_blueprint("sub(ts_zscore(?), ts_mean(?))")
    assert analyze_dimensions(root, 3).error is not None
    assert analyze_dimensions(root, 4).error is None
    assert analyze_dimensions(root).error is None


# ─── Every reachable terminal state passes the full check ────────────────

OPEN_BLUEPRINTS = [
    "sub(ts_mean(?), ts_mean(?))",
    "sub(ts_max(?), ts_mean(?))",
    "greater_than(ts_sum(?), ts_mean(?))",
    "and_(greater_than(?, ?), less_than(ts_zscore(?), ts_corr(?, ?)))",
    "or_(not_(greater_than(?, pv_close)), greater_than(ts_mean(?), ts_min(?)))",
    "mult(ts_zscore(?), ts_corr(pv_volume, ?))",
    "div(ts_mean(?), ts_max(?))",
    "sub(pv_close, ts_mean(?))",
    "add(?, ts_min(?))",
    "ts_rank(?)",
    "mult(?, ?)",
    "sub(div(?, ?), ts_zscore(?))",
]


@pytest.mark.parametrize("max_depth", [3, 4])
@pytest.mark.parametrize("blueprint", OPEN_BLUEPRINTS)
def test_random_completions_always_pass_the_dimension_check(blueprint, max_depth):
    compiler = SemanticCompiler()
    rng = random.Random(zlib.crc32(f"{blueprint}|{max_depth}".encode()))
    for _ in range(60):
        state = MCTSState(compiler.compile_blueprint(blueprint), max_depth=max_depth)
        while not state.is_terminal():
            actions = state.get_actions()
            assert actions, f"dead state in {blueprint}: {state.ast_tree}"
            state = state.apply_action(rng.choice(actions))
        tree = state.ast_tree
        inner = tree.children[0] if tree.name.endswith("_template") else tree
        compiler._check_dimensions(inner)
        # The check must see the finished tree as a whole, templates included.
        assert analyze_dimensions(tree, max_depth).error is None


def test_completion_never_puts_volume_beside_price():
    compiler = SemanticCompiler()
    rng = random.Random(1)
    for _ in range(200):
        state = MCTSState(compiler.compile_blueprint("sub(ts_mean(?), ts_mean(?))"), max_depth=4)
        while not state.is_terminal():
            state = state.apply_action(rng.choice(state.get_actions()))
        text = repr(state.ast_tree)
        assert not ("ts_mean(pv_volume" in text and "ts_mean(pv_close" in text)


# ─── Blueprint acceptance is depth-aware ─────────────────────────────────

DEPTH_5_ONLY = "mult(pv_volume, sub(ts_mean(?), ts_mean(?)))"


def _idea(blueprint):
    return {"name": "n", "timeframe": "10m", "family": "x", "description": "x", "macro_blueprint": blueprint}


def test_depth_limit_constant_is_the_engine_default():
    from strategy_workflows.MCTSEngine import MCTSEngine
    from utilities.AppConfig import MCTS_MAX_DEPTH
    import inspect
    assert inspect.signature(MCTSEngine.__init__).parameters["max_depth"].default == MCTS_MAX_DEPTH


def test_validate_idea_rejects_blueprint_that_needs_more_than_the_depth_limit():
    from strategy_workflows.GenerateStrategies import validate_idea
    with pytest.raises(ValueError, match="Macro-Blueprint Semantic Error.*depth limit"):
        validate_idea(_idea(DEPTH_5_ONLY))
    SemanticCompiler().compile_blueprint(DEPTH_5_ONLY)   # valid when depth is unbounded


def test_validate_idea_accepts_a_completable_blueprint():
    from strategy_workflows.GenerateStrategies import validate_idea
    validate_idea(_idea("sub(ts_mean(?), ts_mean(?))"))


def test_verify_set_rejects_blueprint_that_needs_more_than_the_depth_limit():
    from strategy_workflows.BlueprintGeneration import verify_set
    bad = verify_set([{"name": "deep", "macro_blueprint": DEPTH_5_ONLY}], "current")
    assert len(bad) == 1 and "depth limit" in bad[0]
    ok = verify_set([{"name": "fine", "macro_blueprint": "sub(ts_mean(?), ts_mean(?))"}], "anon_rules")
    assert ok == []
