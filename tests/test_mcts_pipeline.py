import re

import pandas as pd
import pytest

from core_engine.BacktestEngine import AlphaBacktestEngine
from core_engine.CalculateMetrics import compute_metrics
from strategy_workflows.MCTSDimensions import (
    Dimension, OPERATOR_REGISTRY, UNIMPLEMENTED_OPERATORS,
)
from strategy_workflows.MCTSEngine import (
    MCTSEngine, MCTSState, NormalizedMCTSStrategy, ast_to_code, compute_positions,
    describe_candidate, get_operators_for_dimension, get_terminals_for_dimension,
)
from strategy_workflows.RunMCTS import generate_strategy_code
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler
from utilities.Prompts import (
    DIMENSIONAL_FUNCTIONS, FEW_SHOT_EXAMPLES, OPERATOR_FUNCTIONS, build_idea_prompt,
)

TIMEFRAME = '60m'
BLUEPRINT = "sub(ts_mean(?), ts_mean(?))"
SEED = 7
ITERATIONS = 300


def mock_load_data(tf):
    dates = pd.date_range(start='2024-01-01', periods=100, freq='15min')
    return pd.DataFrame({
        'Open': [1000.0] * 100, 'High': [1005.0] * 100, 'Low': [995.0] * 100,
        'Close': [1000.0] * 100, 'Volume': [1000.0] * 100,
    }, index=dates)


@pytest.fixture
def small_engine(monkeypatch):
    monkeypatch.setattr('strategy_workflows.MCTSEngine.load_data', mock_load_data)
    return MCTSEngine(timeframe='10m', seed=1)


def run_search(seed):
    engine = MCTSEngine(timeframe=TIMEFRAME, seed=seed)
    root = SemanticCompiler().compile_blueprint(BLUEPRINT)
    engine.run_search_from_blueprint(root, n_iterations=ITERATIONS)
    return engine


def scored(engine):
    return [c for c in engine.get_best_candidates() if c['reward'] != -10.0]


@pytest.fixture(scope="module")
def searched_engine():
    return run_search(SEED)


# ─── Prompt ──────────────────────────────────────────────────────────────

def test_prompt_few_shot_examples_compile():
    compiler = SemanticCompiler()
    prompt = build_idea_prompt('10m', [], 1, 1)
    assert FEW_SHOT_EXAMPLES
    for _, blueprint in FEW_SHOT_EXAMPLES:
        compiler.compile_blueprint(blueprint)
        assert blueprint in prompt


def test_prompt_lists_exactly_the_supported_operators():
    library = DIMENSIONAL_FUNCTIONS + OPERATOR_FUNCTIONS
    for op in OPERATOR_REGISTRY:
        if op in UNIMPLEMENTED_OPERATORS:
            assert not re.search(rf"\b{op}\b", library)
        else:
            assert op in library
    for talib_name in ("macd_line", "bbands_upper", "stoch_k", "self.feat"):
        assert talib_name not in library


def test_prompt_without_experience_log_has_explicit_empty_section():
    prompt = build_idea_prompt('10m', [], 1, 1, experience="")
    assert "No experience log is available" in prompt


# ─── Expansion and rendering ─────────────────────────────────────────────

def test_boolean_and_any_slots_expand():
    for dim in (Dimension.BOOLEAN, Dimension.ANY):
        get_terminals_for_dimension(dim)
        assert get_operators_for_dimension(dim)
    assert all(
        OPERATOR_REGISTRY[op.name]["output_dim"] == Dimension.BOOLEAN
        for op in get_operators_for_dimension(Dimension.BOOLEAN)
    )
    assert not any(t.name == "pv_vn30_close" for t in get_terminals_for_dimension(Dimension.ANY))


def test_boolean_blueprint_rollout_reaches_terminal_state():
    import random
    root = SemanticCompiler().compile_blueprint("and_(?, ?)")
    rng = random.Random(0)
    for _ in range(20):
        state = MCTSState(root, max_depth=4)
        while not state.is_terminal():
            actions = state.get_actions()
            assert actions, "non-terminal state without actions"
            state = state.apply_action(rng.choice(actions))
        assert "?" not in ast_to_code(state.ast_tree)


def test_window_is_fixed_on_the_node():
    state = MCTSState(SemanticCompiler().compile_blueprint(BLUEPRINT), max_depth=4)
    while not state.is_terminal():
        state = state.apply_action(state.get_actions()[-1])
    tree = state.ast_tree
    code = ast_to_code(tree.children[0])
    assert all(ast_to_code(tree.children[0]) == code for _ in range(20))
    assert describe_candidate(tree)['cache_key'] == describe_candidate(tree)['cache_key']


def test_ts_node_without_window_cannot_render():
    with pytest.raises(ValueError, match="no window"):
        ast_to_code(ASTNode(name="ts_mean", children=[ASTNode(name="pv_close")]))


def test_unimplemented_operator_blueprint_is_rejected(small_engine):
    root = SemanticCompiler().compile_blueprint("crossed_above(ts_mean(?), ts_mean(?))")
    with pytest.raises(ValueError, match="crossed_above"):
        small_engine.run_search_from_blueprint(root, n_iterations=5)


def test_evaluation_errors_are_counted_not_swallowed(small_engine):
    # A rolling mean of a scalar (constant + constant) cannot be evaluated.
    scalar = ASTNode(name="add", children=[ASTNode(name="Constant", value=1.0), ASTNode(name="Constant", value=2.0)])
    bad = ASTNode(name="ts_mean", children=[scalar], window=3)
    tree = ASTNode(name="normalized_template", children=[
        bad, ASTNode(name="window", value=5), ASTNode(name="z_score", value=1.0)])
    reward, _, _ = small_engine.evaluate_expression(tree)
    assert reward == -10.0
    summary = small_engine.error_summary()
    assert summary['failed_evaluations'] == 1
    assert summary['top_errors'][0][0].startswith("ValueError")


# ─── End to end on real data ─────────────────────────────────────────────

@pytest.mark.slow
def test_ts_blueprint_yields_candidate_with_reward_other_than_minus_10(searched_engine):
    good = scored(searched_engine)
    assert good, searched_engine.error_summary()
    assert all(c['reward'] > 0 for c in good)
    assert good[0]['metrics']['template'] == "NORMALIZED"


@pytest.mark.slow
def test_same_seed_gives_same_search(searched_engine):
    again = run_search(SEED)
    first = [(c['expr'], c['reward'], c['direction'], c['window']) for c in searched_engine.get_best_candidates()]
    second = [(c['expr'], c['reward'], c['direction'], c['window']) for c in again.get_best_candidates()]
    assert first == second
    assert scored(searched_engine)[0]['expr'] == scored(again)[0]['expr']


@pytest.mark.slow
def test_exported_strategy_reproduces_engine_score(searched_engine):
    cand = scored(searched_engine)[0]
    code = generate_strategy_code(
        cand['expr'], cand['direction'], 0.2, cand['template'], cand['window'],
        cand['z_score'], cand['threshold_upper'], cand['threshold_lower'],
    )
    namespace = {}
    exec(compile(code, "<exported_strategy>", "exec"), namespace)
    df = searched_engine.df_search
    exported = namespace['CustomStrategy']()
    result = AlphaBacktestEngine().run(exported, df)
    metrics = compute_metrics(result)

    assert metrics['calmar_ratio'] == pytest.approx(cand['metrics']['calmar_ratio'])
    assert metrics['total_trades'] == cand['metrics']['total_trades']

    # Positions must equal those the search scored, from the export and from the RunMCTS replay class.
    from strategy_workflows.MCTSEngine import evaluate_alpha
    expected = compute_positions(
        cand['template'], evaluate_alpha(cand['expr'], searched_engine.data), cand['direction'], 0.2,
        cand['window'], cand['z_score'],
    )
    assert (expected != 0).any()
    pd.testing.assert_series_equal(exported.run_algorithm(df), expected, check_names=False)
    replay = NormalizedMCTSStrategy(
        expr_str=cand['expr'], direction=cand['direction'], position_scale=0.2,
        window=cand['window'], z_score_threshold=cand['z_score'],
    ).run_algorithm(df)
    pd.testing.assert_series_equal(replay, expected, check_names=False)
