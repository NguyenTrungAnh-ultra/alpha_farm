import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# MCTS Engine for Alpha Discovery - Unified Compiler Architecture
import os
import sys
import math
import random
import time
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import hashlib

from core_engine.XnoEngine import SimpleAlgorithm
from core_engine.BacktestEngine import XNOBacktestEngine, load_data
from core_engine.GenerateReport import compute_metrics
from strategy_workflows.MCTSDimensions import Dimension, OPERATOR_REGISTRY, get_operators_by_return_dim, DATA_FIELD_DIMENSIONS, OperatorGroup
from strategy_workflows.PortfolioManager import PortfolioManager
from strategy_workflows.SemanticCompiler import ASTNode

PERIODS = [5, 10, 14, 20, 30, 60]

def ast_to_code(node: ASTNode) -> str:
    """Translates the AST node and its children to Python code string."""
    if node.name == "?":
        return '?'
    
    if node.name == "Constant":
        return str(node.value)
        
    if node.name in DATA_FIELD_DIMENSIONS:
        feature_mapping = {
            'close': 'close',
            'open': 'open_',
            'high': 'high',
            'low': 'low',
            'volume': 'volume',
            'pv_vn30_close': 'self.data.pv_vn30_close'
        }
        # Backward compatibility for old names
        if node.name.startswith("pv_"):
            return feature_mapping.get(node.name[3:], node.name)
        return feature_mapping.get(node.name, node.name)

    if node.name not in OPERATOR_REGISTRY:
        raise ValueError(f"Unknown operator: {node.name}")
        
    group = OPERATOR_REGISTRY[node.name]["group"]
    
    # Render operators
    if group == OperatorGroup.STATISTICS and node.name in ['add', 'sub', 'mult', 'div']:
        op_map = {'add': '+', 'sub': '-', 'mult': '*', 'div': '/'}
        if node.name == 'div':
            return f"({ast_to_code(node.children[0])} / ({ast_to_code(node.children[1])} + 1e-8))"
        return f"({ast_to_code(node.children[0])} {op_map[node.name]} {ast_to_code(node.children[1])})"
        
    if group == OperatorGroup.LOGIC and node.name in ['and_', 'or_', 'not_', 'greater_than', 'less_than', 'equal']:
        if node.name == 'not_':
            return f"(~{ast_to_code(node.children[0])})"
        if node.name in ['greater_than', 'less_than', 'equal']:
            op_map = {'greater_than': '>', 'less_than': '<', 'equal': '=='}
            return f"({ast_to_code(node.children[0])} {op_map[node.name]} {ast_to_code(node.children[1])})"
        op_map = {'and_': '&', 'or_': '|'}
        return f"({ast_to_code(node.children[0])} {op_map[node.name]} {ast_to_code(node.children[1])})"

    # General function call: self.op or self.feat
    prefix = "self.op" if group in [OperatorGroup.LOGIC, OperatorGroup.TIME_SERIES] else "self.feat"
    
    # Candlestick (Leaf Features)
    if group == OperatorGroup.CANDLESTICK:
        return f"{prefix}.{node.name}(open_, high, low, close)"

    # Component Splitting Renderings
    if node.name == 'macd_line':
        return f"self.feat.macd({ast_to_code(node.children[0])})[0]"
    if node.name == 'macd_signal':
        return f"self.feat.macd({ast_to_code(node.children[0])})[1]"
    if node.name == 'macd_hist':
        return f"self.feat.macd({ast_to_code(node.children[0])})[2]"
    if node.name == 'bbands_upper':
        return f"self.feat.bbands({ast_to_code(node.children[0])})[0]"
    if node.name == 'bbands_middle':
        return f"self.feat.bbands({ast_to_code(node.children[0])})[1]"
    if node.name == 'bbands_lower':
        return f"self.feat.bbands({ast_to_code(node.children[0])})[2]"

    # Arity 0 Terminal nodes requiring internal variables
    if node.name == 'vwap':
        return "self.feat.vwap(high, low, close, volume)"
    if node.name == 'adx':
        return f"self.feat.adx(high, low, close, timeperiod={random.choice(PERIODS)})"
    if node.name == 'stoch_k':
        return f"self.feat.stoch(high, low, close)[0]"
    if node.name == 'stoch_d':
        return f"self.feat.stoch(high, low, close)[1]"

    args = []
    for c in node.children:
        args.append(ast_to_code(c))
    
    # Safely inject keyword arguments
    if not any(isinstance(c, ASTNode) and c.name == "Constant" for c in node.children):
        if node.name in ['ema', 'rsi', 'stddev', 'var', 'zscore']:
            args.append(f"timeperiod={random.choice(PERIODS)}")
        elif node.name in ['shift', 'diff', 'pct_change']:
            args.append(f"periods={random.choice([1, 2, 3, 5, 10])}")
            
    return f"{prefix}.{node.name}({', '.join(args)})"

def clone_ast(node: ASTNode) -> ASTNode:
    return ASTNode(
        name=node.name,
        children=[clone_ast(c) for c in node.children],
        value=node.value
    )

def find_first_placeholder(node: ASTNode) -> Optional[ASTNode]:
    """Depth-first search to find the first placeholder node ('?')."""
    if node.name == '?':
        return node
    for child in node.children:
        ph = find_first_placeholder(child)
        if ph is not None:
            return ph
    return None

def get_node_depth(root: ASTNode, target: ASTNode, current_depth: int = 0) -> Optional[int]:
    if root is target:
        return current_depth
    for child in root.children:
        d = get_node_depth(child, target, current_depth + 1)
        if d is not None:
            return d
    return None

# MCTS Expansions
def get_terminals_for_dimension(dim: Dimension) -> List[ASTNode]:
    """Returns possible leaf expansions for a given dimension."""
    terminals = []
    for field, field_dim in DATA_FIELD_DIMENSIONS.items():
        if field_dim == dim or dim == Dimension.ANY:
            terminals.append(ASTNode(name=field))
            
    if dim == Dimension.RATIO or dim == Dimension.ANY:
        for val in [0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]:
            terminals.append(ASTNode(name="Constant", value=val))
            
    if dim == Dimension.BOOLEAN or dim == Dimension.ANY:
        # Candlesticks are leaf boolean features
        for op, meta in OPERATOR_REGISTRY.items():
            if meta["group"] == OperatorGroup.CANDLESTICK:
                terminals.append(ASTNode(name=op))
                
    return terminals

def get_operators_for_dimension(dim: Dimension) -> List[ASTNode]:
    """Backward Chaining & Arity Matching"""
    ops = []
    allowed_ops = get_operators_by_return_dim(dim)
    
    for op in allowed_ops:
        meta = OPERATOR_REGISTRY[op]
        # Arity Matching: Generate placeholders based on input_dims
        children = []
        for expected_dim in meta["input_dims"]:
            # We attach the expected dimension to the placeholder value so MCTS knows what to fill next
            children.append(ASTNode(name='?', value=expected_dim))
        ops.append(ASTNode(name=op, children=children))
    return ops

class MCTSState:
    def __init__(self, ast_tree: ASTNode, max_depth: int = 3):
        self.ast_tree = ast_tree
        self.max_depth = max_depth

    def is_terminal(self) -> bool:
        return find_first_placeholder(self.ast_tree) is None

    def get_actions(self) -> List[ASTNode]:
        ph = find_first_placeholder(self.ast_tree)
        if ph is None:
            return []
        
        # The expected dimension was stashed in the placeholder's value field
        req_dim = ph.value if isinstance(ph.value, Dimension) else Dimension.ANY
        
        depth = get_node_depth(self.ast_tree, ph)
        if depth is not None and depth >= self.max_depth:
            return get_terminals_for_dimension(req_dim)
        
        return get_terminals_for_dimension(req_dim) + get_operators_for_dimension(req_dim)

    def apply_action(self, action_node: ASTNode) -> 'MCTSState':
        new_tree = clone_ast(self.ast_tree)
        ph = find_first_placeholder(new_tree)
        if ph is not None:
            ph.name = action_node.name
            ph.children = [clone_ast(child) for child in action_node.children]
            ph.value = action_node.value
        return MCTSState(new_tree, self.max_depth)

class MCTSNode:
    def __init__(self, state: MCTSState, parent: Optional['MCTSNode'] = None, action_leading_here: Optional[ASTNode] = None):
        self.state = state
        self.parent = parent
        self.action_leading_here = action_leading_here
        self.children: List['MCTSNode'] = []
        self.visit_count = 0
        self.max_reward = -float('inf') # Risk-Seeking Optimization (Tail Quantile)
        self.untried_actions = state.get_actions()

    def is_fully_expanded(self) -> bool:
        return len(self.untried_actions) == 0

    def is_leaf(self) -> bool:
        return len(self.children) == 0

class DynamicMCTSStrategy(SimpleAlgorithm):
    position_scale = 0.2

    def __algorithm__(self):
        expr_str = self.expr_str
        direction = self.direction
        pos_scale = self.position_scale
        
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        open_ = self.data.pv_open
        volume = self.data.pv_volume
        
        globals_dict = {
            'self': self,
            'close': close,
            'high': high,
            'low': low,
            'open_': open_,
            'volume': volume
        }
        
        try:
            alpha_val = eval(expr_str, {}, globals_dict)
            self.alpha_series = alpha_val
        except Exception:
            self.alpha_series = close * 0.0
            alpha_val = close * 0.0

        window = 20
        r_mean = self.feat.rolling_mean(alpha_val, window)
        r_std = self.feat.rolling_std(alpha_val, window) + 1e-8
        
        z_score = (alpha_val - r_mean) / r_std
        z_score = z_score * direction

        raw_pos = self.op.where(z_score > 1.0, pos_scale, self.op.where(z_score < -1.0, -pos_scale, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == pos_scale
        short_mask = raw_pos == -pos_scale
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position=pos_scale)
        self.set_positions(short_mask, position=-pos_scale)

import inspect
DynamicMCTSStrategy._emulator_source_code = inspect.getsource(DynamicMCTSStrategy)

class MCTSEngine:
    def __init__(self, timeframe: str = '10m', max_depth: int = 4, exploration_c: float = 1.414):
        self.timeframe = timeframe
        self.max_depth = max_depth
        self.exploration_c = exploration_c
        
        print(f"[MCTS] Loading data for {timeframe}...")
        self.df = load_data(timeframe)
        self.df['Volume'] = self.df['Volume'].fillna(0.0)
        self.df_search = self.df['2023-01-01':]
        if len(self.df_search) < 100:
            self.df_search = self.df
            
        self.backtest_engine = XNOBacktestEngine()
        self.cache: Dict[str, tuple] = {}
        self.leaderboard: List[Dict[str, Any]] = []
        
        # Frequent Subtree Avoidance (FSA) Rolling Cache
        # Stores SHA256 hashes of AST string representations of top alphas
        self.fsa_cache: set = set()

    def add_to_fsa_cache(self, ast_str: str):
        """Adds structure to FSA cache to prevent duplicate genetics."""
        h = hashlib.sha256(ast_str.encode()).hexdigest()
        self.fsa_cache.add(h)
        
    def is_in_fsa_cache(self, ast_str: str) -> bool:
        h = hashlib.sha256(ast_str.encode()).hexdigest()
        return h in self.fsa_cache

    def compute_rank_ic(self, alpha_series: pd.Series, close_series: pd.Series) -> float:
        fwd_returns = close_series.pct_change(1).shift(-1)
        valid = pd.DataFrame({'alpha': alpha_series, 'fwd_ret': fwd_returns}).dropna()
        if len(valid) < 20:
            return 0.0
        # Prevent pandas ConstantInput warning when input series is constant (standard deviation is 0)
        if valid['alpha'].std() == 0.0 or valid['fwd_ret'].std() == 0.0:
            return 0.0
        return valid['alpha'].corr(valid['fwd_ret'], method='spearman')

    def evaluate_expression(self, ast_tree: ASTNode) -> tuple:
        expr_str = ast_to_code(ast_tree)
        if expr_str in self.cache:
            return self.cache[expr_str]
            
        # FSA Check - Penalty for genetic duplication
        if self.is_in_fsa_cache(expr_str):
            return -100.0, 1.0, {} # Massive penalty for identical subtree
            
        best_reward = -10.0
        best_direction = 1.0
        best_metrics = {}
        
        for direction in [1.0, -1.0]:
            try:
                strategy = DynamicMCTSStrategy(expr_str=expr_str, direction=direction)
                result = self.backtest_engine.run(strategy, self.df_search)
                metrics = compute_metrics(result)
                
                raw_alpha = strategy.alpha_series._data if hasattr(strategy.alpha_series, '_data') else strategy.alpha_series
                rank_ic = self.compute_rank_ic(raw_alpha, self.df_search['Close'])
                
                sharpe = metrics.get('sharpe_ratio', 0.0)
                if np.isnan(sharpe):
                    sharpe = 0.0
                    
                total_trades = metrics.get('total_trades', 0)
                if total_trades < 15:
                    reward = 0.0
                else:
                    reward = 10.0 * abs(rank_ic) + max(0.0, sharpe)
                    
                if reward > best_reward:
                    best_reward = reward
                    best_direction = direction
                    best_metrics = metrics
                    best_metrics['rank_ic'] = rank_ic
            except Exception as e:
                pass
                
        self.cache[expr_str] = (best_reward, best_direction, best_metrics)
        return best_reward, best_direction, best_metrics

    def run_search_from_blueprint(self, root_ast: ASTNode, n_iterations: int = 100):
        """Unified Compiler Architecture: Starts from an AST parsed from LLM Blueprint JSON."""
        root_state = MCTSState(root_ast, self.max_depth)
        root_node = MCTSNode(root_state)
        
        print(f"[MCTS] Starting unified search from Blueprint | Depth: {self.max_depth} | Iterations: {n_iterations}")
        
        start_time = time.time()
        for i in range(1, n_iterations + 1):
            if i % 10 == 0:
                elapsed = time.time() - start_time
                print(f"  [MCTS] Iteration {i}/{n_iterations} | Cache size: {len(self.cache)} | Best reward: {max([x['reward'] for x in self.leaderboard]) if self.leaderboard else 'N/A'} | Elapsed: {elapsed:.1f}s")
                
            node = root_node
            path = [node]
            while node.is_fully_expanded() and not node.is_leaf():
                node = self.select_best_child(node)
                path.append(node)
                
            if not node.state.is_terminal():
                if not node.is_fully_expanded():
                    action = node.untried_actions.pop(random.randrange(len(node.untried_actions)))
                    new_state = node.state.apply_action(action)
                    child_node = MCTSNode(new_state, parent=node, action_leading_here=action)
                    node.children.append(child_node)
                    node = child_node
                    path.append(node)
                    
            terminal_state = self.rollout(node.state)
            reward, direction, metrics = self.evaluate_expression(terminal_state.ast_tree)
            
            if terminal_state.is_terminal():
                expr_code = ast_to_code(terminal_state.ast_tree)
                self.update_leaderboard(expr_code, reward, direction, metrics)
                
                # Update FSA Rolling Window Cache if good reward
                if reward > 1.0:
                    self.add_to_fsa_cache(expr_code)
                
            # Risk-Seeking Backpropagation (Tail Quantile)
            for p_node in path:
                p_node.visit_count += 1
                if reward > p_node.max_reward:
                    p_node.max_reward = reward

        print(f"[MCTS] Search completed in {time.time() - start_time:.1f}s.")

    def select_best_child(self, node: MCTSNode) -> MCTSNode:
        """Selects child that maximizes UCT using MAX reward (Risk-seeking)."""
        best_uct = -1e9
        best_child = None
        log_parent_visits = math.log(node.visit_count)
        
        for child in node.children:
            if child.visit_count == 0:
                uct = 1e9
            else:
                # Use max_reward instead of mean_reward for Tail Quantile optimization
                exploit = child.max_reward 
                exploration = self.exploration_c * math.sqrt(log_parent_visits / child.visit_count)
                uct = exploit + exploration
                
            if uct > best_uct:
                best_uct = uct
                best_child = child
                
        return best_child or random.choice(node.children)

    def rollout(self, state: MCTSState) -> MCTSState:
        curr_state = state
        while not curr_state.is_terminal():
            actions = curr_state.get_actions()
            if not actions:
                break
            action = random.choice(actions)
            curr_state = curr_state.apply_action(action)
        return curr_state

    def update_leaderboard(self, expr_str: str, reward: float, direction: float, metrics: dict):
        for item in self.leaderboard:
            if item['expr'] == expr_str:
                return
        
        self.leaderboard.append({
            'expr': expr_str,
            'reward': reward,
            'direction': direction,
            'metrics': metrics
        })
        self.leaderboard.sort(key=lambda x: x['reward'], reverse=True)
        self.leaderboard = self.leaderboard[:100] # Rolling Window Cache bounds

    def get_best_candidates(self) -> List[Dict[str, Any]]:
        return self.leaderboard
