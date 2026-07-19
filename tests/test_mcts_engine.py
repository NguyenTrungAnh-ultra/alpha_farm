import pytest
import math
import pandas as pd
from strategy_workflows.MCTSEngine import MCTSEngine, MCTSNode, MCTSState
from strategy_workflows.SemanticCompiler import ASTNode
from utilities.AppConfig import BASELINE_TF_MINUTES, BASE_PERIODS, BASE_WINDOW_SEARCH

def mock_load_data(tf):
    dates = pd.date_range(start='2024-01-01', periods=100, freq='15min')
    return pd.DataFrame({
        'Open': [1000.0]*100,
        'High': [1005.0]*100,
        'Low': [995.0]*100,
        'Close': [1000.0]*100,
        'Volume': [1000.0]*100
    }, index=dates)

def test_scale_mismatch(monkeypatch):
    monkeypatch.setattr('strategy_workflows.MCTSEngine.load_data', mock_load_data)
    
    # '1m' timeframe tests the scaling
    engine_1m = MCTSEngine(timeframe='1m')
    
    # baseline = 10 minutes, timeframe = 1m => scale = 10
    scale = BASELINE_TF_MINUTES / 1
    
    expected_periods = sorted(set(max(2, round(p * scale)) for p in BASE_PERIODS))
    expected_window_search = sorted(set(max(2, round(w * scale)) for w in BASE_WINDOW_SEARCH))
    
    assert engine_1m.scaled_periods == expected_periods
    assert engine_1m.scaled_window_search == expected_window_search

def test_ucb1_logic(monkeypatch):
    monkeypatch.setattr('strategy_workflows.MCTSEngine.load_data', mock_load_data)
    
    engine = MCTSEngine(timeframe='10m')
    
    dummy_ast = ASTNode("dummy")
    state = MCTSState(dummy_ast)
    parent_node = MCTSNode(state)
    parent_node.visit_count = 10
    
    # Child 1 with 0 visits (should have infinity UCB1)
    child1 = MCTSNode(state, parent=parent_node)
    child1.visit_count = 0
    
    # Child 2 with 2 visits and some reward
    child2 = MCTSNode(state, parent=parent_node)
    child2.visit_count = 2
    child2.max_reward = 5.0
    
    parent_node.children = [child1, child2]
    
    best = engine.select_best_child(parent_node)
    assert best == child1, "Expected child with 0 visits to be selected due to infinity UCB1"
    
    # Now simulate some visits on child 1, but poor reward
    child1.visit_count = 5
    child1.max_reward = -2.0
    
    # child1 ucb1: exploit=-2.0, exploration=1.414 * sqrt(ln(10) / 5) ~ 0.96 => ~ -1.04
    # child2 ucb1: exploit=5.0, exploration=1.414 * sqrt(ln(10) / 2) ~ 1.51 => ~ 6.51
    # child2 should win
    best2 = engine.select_best_child(parent_node)
    assert best2 == child2, "Expected child with higher UCB1 value to be selected"
