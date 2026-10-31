import numpy as np
import pandas as pd
import pytest

from strategy_workflows.MCTSDimensions import Dimension, analyze_dimensions
from strategy_workflows.MCTSEngine import MCTSEngine, MCTSState
from strategy_workflows.RandomSearch import template_root
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler


@pytest.fixture
def frame():
    rng = np.random.default_rng(3)
    index = pd.date_range('2024-01-01', periods=700, freq='h', name='Datetime')
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.002, len(index)))
    return pd.DataFrame({
        'Open': close * rng.uniform(0.999, 1.001, len(index)), 'High': close * rng.uniform(1.0, 1.003, len(index)),
        'Low': close * rng.uniform(0.997, 1.0, len(index)), 'Close': close,
        'Volume': rng.uniform(1000, 5000, len(index)),
    }, index=index)


def engine_for(frame, seed=5):
    return MCTSEngine(timeframe='60m', data=frame, seed=seed, reward_mode='sharpe', global_position_matrix=None)


def board(engine):
    return [(item['expr'], item['template'], item['reward'], item['direction'], item['window'], item['z_score'])
            for item in engine.leaderboard]


BLUEPRINT = "sub(ts_mean(?), ts_mean(?))"


def test_chunked_session_reproduces_one_long_search(frame):
    whole = engine_for(frame)
    whole.run_search_from_blueprint(SemanticCompiler().compile_blueprint(BLUEPRINT), n_iterations=120)

    chunked = engine_for(frame)
    session = chunked.start_search(SemanticCompiler().compile_blueprint(BLUEPRINT))
    for _ in range(6):
        chunked.continue_search(session, 20, early_stop=False)

    assert session.iterations == 120
    assert board(chunked) == board(whole)
    assert chunked.evaluation_count == whole.evaluation_count
    assert chunked.rng.random() == whole.rng.random()


def test_two_sessions_interleaved_keep_separate_trees(frame):
    engine = engine_for(frame)
    compiler = SemanticCompiler()
    first = engine.start_search(compiler.compile_blueprint(BLUEPRINT))
    second = engine.start_search(compiler.compile_blueprint("ts_max(?)"))
    for _ in range(3):
        engine.continue_search(first, 10, early_stop=False)
        engine.continue_search(second, 10, early_stop=False)
    assert (first.iterations, second.iterations) == (30, 30)
    assert first.root_node is not second.root_node
    assert first.root_node.visit_count == 30 and second.root_node.visit_count == 30


def test_patience_and_entropy_counters_live_in_the_session(frame, monkeypatch):
    from strategy_workflows import MCTSEngine as engine_module
    monkeypatch.setitem(engine_module.REWARD_WEIGHTS, 'patience', 8)
    engine = engine_for(frame)
    session = engine.start_search(SemanticCompiler().compile_blueprint("ts_max(?)"))
    reasons = []
    for _ in range(12):
        reasons.append(engine.continue_search(session, 5))
    assert "patience" in reasons
    ran = session.iterations
    assert engine.continue_search(session, 50) == "patience" and session.iterations == ran

    off = engine_for(frame)
    session = off.start_search(SemanticCompiler().compile_blueprint("ts_max(?)"))
    assert off.continue_search(session, 60, early_stop=False) == "budget" and session.iterations == 60


def test_bare_question_mark_root_is_a_boolean_root():
    root = template_root('BOOLEAN')
    analysis = analyze_dimensions(root, 4)
    assert analysis.error is None
    assert analysis.root_dims == frozenset({Dimension.BOOLEAN})
    assert analysis.slot_dims[id(root)] == frozenset({Dimension.BOOLEAN})
    names = {a.name for a in MCTSState(root, 4).get_actions()}
    assert names == {'and_', 'or_', 'not_', 'greater_than', 'less_than', 'equal'}


@pytest.mark.parametrize("template, expected_root", [
    ('NORMALIZED', {Dimension.CURRENCY, Dimension.VOLUME, Dimension.RATIO}),
    ('RATIO', {Dimension.RATIO}),
])
def test_template_roots_take_numeric_slots(template, expected_root):
    root = template_root(template)
    analysis = analyze_dimensions(root, 4)
    assert analysis.error is None
    slot = root.children[0]
    assert set(analysis.slot_dims[id(slot)]) == expected_root


def test_every_template_root_can_start_a_search(frame):
    engine = engine_for(frame)
    for template in ('NORMALIZED', 'BOOLEAN', 'RATIO'):
        session = engine.start_search(template_root(template))
        engine.continue_search(session, 15, early_stop=False)
        assert session.iterations == 15


def test_a_blueprint_that_cannot_complete_is_refused_at_start(frame):
    engine = engine_for(frame)
    bad = SemanticCompiler().compile_blueprint("mult(pv_volume, sub(ts_mean(?), ts_mean(?)))")
    with pytest.raises(ValueError, match="cannot be completed"):
        engine.start_search(bad)
    crossed = ASTNode(name='crossed', children=[ASTNode(name='?'), ASTNode(name='?')])
    with pytest.raises(ValueError, match="no code generation"):
        engine.start_search(crossed)
