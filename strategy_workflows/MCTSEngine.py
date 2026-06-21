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
from utilities.AppConfig import REWARD_WEIGHTS

PERIODS = [5, 10, 14, 20, 30, 60]

def ast_to_code(node: ASTNode) -> str:
    """Translates the AST node and its children to Python code string."""
    if node.name == "?":
        return '?'
    
    if node.name in ["Constant", "z_score", "window"]:
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
    if node.name in ('window', 'z_score') and node.value == '?':
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
    """
    Represents a state in the Monte Carlo Tree Search.
    
    Note on Depth:
        `MCTSState` defaults to a `max_depth` of 3. However, when run from
        `MCTSEngine`, the engine's `max_depth` (which defaults to 4) is passed
        down and overrides this default value.
    """
    def __init__(self, ast_tree: ASTNode, max_depth: int = 3):
        """
        Initialize the MCTSState.
        
        Parameters
        ----------
        ast_tree : ASTNode
            The current AST tree representing the formula.
        max_depth : int, default 3
            The maximum allowed depth for tree expansion. Typically overridden 
            by MCTSEngine's max_depth (default 4).
        """
        self.ast_tree = ast_tree
        self.max_depth = max_depth

    def is_terminal(self) -> bool:
        return find_first_placeholder(self.ast_tree) is None

    def get_actions(self) -> List[ASTNode]:
        ph = find_first_placeholder(self.ast_tree)
        if ph is None:
            return []
            
        if ph.name == 'window':
            return [ASTNode(name='window', value=v) for v in [5, 10, 14, 20, 30, 40, 60]]
        if ph.name == 'z_score':
            return [ASTNode(name='z_score', value=v) for v in [0.5, 1.0, 1.5, 2.0, 2.5]]
        
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
            if ph.name in ('window', 'z_score'):
                ph.value = action_node.value
            else:
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
    window = 20
    z_score_threshold = 1.0

    def __algorithm__(self):
        expr_str = self.expr_str
        direction = self.direction
        pos_scale = self.position_scale
        
        # Get dynamically discovered parameters, fallback to defaults
        window = self.window
        z_score_threshold = self.z_score_threshold
        
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

        r_mean = self.feat.rolling_mean(alpha_val, window)
        r_std = self.feat.rolling_std(alpha_val, window) + 1e-8
        
        z_score = (alpha_val - r_mean) / r_std
        z_score = z_score * direction

        raw_pos = self.op.where(z_score > z_score_threshold, pos_scale, self.op.where(z_score < -z_score_threshold, -pos_scale, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == pos_scale
        short_mask = raw_pos == -pos_scale
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position=pos_scale)
        self.set_positions(short_mask, position=-pos_scale)

import inspect
DynamicMCTSStrategy._emulator_source_code = inspect.getsource(DynamicMCTSStrategy)

class MCTSEngine:
    """
    Monte Carlo Tree Search Engine for alpha expression discovery.
    
    Note on Depth:
        `MCTSEngine` defaults to a `max_depth` of 4. When creating an `MCTSState`, 
        the engine overrides the state's default `max_depth` of 3 with its own 
        configured depth (typically 4).
    """
    def __init__(self, timeframe: str = '10m', max_depth: int = 4, exploration_c: float = 1.414, global_position_matrix: pd.DataFrame = None):
        """
        Initialize the MCTSEngine.
        
        Parameters
        ----------
        timeframe : str, default '10m'
            The data timeframe to load and run backtests on.
        max_depth : int, default 4
            The maximum formula tree depth. Overrides MCTSState's default of 3.
        exploration_c : float, default 1.414
            Exploration constant for UCT child selection.
        global_position_matrix : Optional[pd.DataFrame], default None
            Matrix of historical position series used for correlation penalty.
        """
        self.timeframe = timeframe
        self.max_depth = max_depth
        self.exploration_c = exploration_c
        self.global_position_matrix = global_position_matrix
        
        print(f"[MCTS] Loading data for {timeframe}...")
        self.df = load_data(timeframe)
        self.df['Volume'] = self.df['Volume'].fillna(0.0)
        # Use full historical data for MCTS due to vectorized engine speedup
        self.df_search = self.df
            
        self.backtest_engine = XNOBacktestEngine()
        self.cache: Dict[str, tuple] = {}
        self.max_cache_size = 50000
        self.leaderboard: List[Dict[str, Any]] = []
        
        # Reusable temporary strategy to avoid object-recreation overhead in evaluate_expression
        self.temp_strat = DynamicMCTSStrategy()
        self.temp_strat._initialize(self.df_search)
        
        # Frequent Subtree Avoidance (FSA) Rolling Cache
        # Stores SHA256 hashes of AST string representations of top alphas
        self.fsa_cache: set = set()

    def add_to_fsa_cache(self, ast_str: str):
        """
        Add the SHA256 hash of an AST string to the Frequent Subtree Avoidance (FSA) cache.
        
        This cache prevents genetic duplication by tracking structures that have
        already yielded promising candidates, avoiding redundant search paths.
        
        Parameters
        ----------
        ast_str : str
            The string representation of the AST node or expression.
        """
        h = hashlib.sha256(ast_str.encode()).hexdigest()
        self.fsa_cache.add(h)
        
    def is_in_fsa_cache(self, ast_str: str) -> bool:
        """
        Check if the SHA256 hash of an AST string exists in the FSA cache.
        
        Parameters
        ----------
        ast_str : str
            The string representation of the AST node or expression to check.
            
        Returns
        -------
        bool
            True if the hash exists in the FSA cache, False otherwise.
        """
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
        """
        Evaluate the trading performance of an AST tree by running a backtest.
        
        Uses an evaluation cache (`self.cache`) to store previous backtest results
        based on the generated expression string, window, and z-score threshold.
        Also checks the FSA cache to penalize duplicate subtrees with a large
        negative reward.
        
        Applies One-pass Pipeline rules:
        - Hard filter: Calmar Ratio < 1.1 -> reward = -10.0
        - Position correlation penalty against global_position_matrix
        - Multi-objective reward: (0.6 * S_calmar + 0.4 * S_ic) * S_corr
        
        Parameters
        ----------
        ast_tree : ASTNode
            The AST tree representing the strategy or formula.
            
        Returns
        -------
        tuple
            A tuple of (best_reward, best_direction, best_metrics)
        """
        if ast_tree.name == "strategy_root":
            window = ast_tree.children[0].value
            z_score_thresh = ast_tree.children[1].value
            alpha_node = ast_tree.children[2]
            expr_str = ast_to_code(alpha_node)
        else:
            window = 20
            z_score_thresh = 1.0
            expr_str = ast_to_code(ast_tree)
            
        cache_key = f"{expr_str}_{window}_{z_score_thresh}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        # FSA Check - Penalty for genetic duplication
        if self.is_in_fsa_cache(cache_key):
            return -100.0, 1.0, {} # Massive penalty for identical subtree
            
        best_reward = -10.0
        best_direction = 1.0
        best_metrics = {}
        
        # Fast Dual-Direction Evaluation
        # Instead of parsing and computing rolling metrics twice, we do it ONCE.
        try:
            globals_dict = {
                'self': self.temp_strat,
                'close': self.temp_strat.data.pv_close,
                'high': self.temp_strat.data.pv_high,
                'low': self.temp_strat.data.pv_low,
                'open_': self.temp_strat.data.pv_open,
                'volume': self.temp_strat.data.pv_volume
            }
            
            try:
                alpha_val = eval(expr_str, {}, globals_dict)
            except Exception:
                alpha_val = self.temp_strat.data.pv_close * 0.0
                
            r_mean = self.temp_strat.feat.rolling_mean(alpha_val, window)
            r_std = self.temp_strat.feat.rolling_std(alpha_val, window) + 1e-8
            z_score_base = (alpha_val - r_mean) / r_std
            
            # Rank IC can be computed on the base alpha directly
            raw_alpha = alpha_val._data if hasattr(alpha_val, '_data') else alpha_val
            rank_ic = self.compute_rank_ic(raw_alpha, self.df_search['Close'])
            
            pos_scale = self.temp_strat.position_scale
            
            # Long positions
            z_long = z_score_base
            pos_long = self.temp_strat.op.where(z_long > z_score_thresh, pos_scale, self.temp_strat.op.where(z_long < -z_score_thresh, -pos_scale, 0.0))
            
            # Short positions
            z_short = z_score_base * -1.0
            pos_short = self.temp_strat.op.where(z_short > z_score_thresh, pos_scale, self.temp_strat.op.where(z_short < -z_score_thresh, -pos_scale, 0.0))
            
            class PrecalcStrategy:
                def __init__(self, p):
                    self.p = p
                def run_algorithm(self, df):
                    return self.p
                    
            scenarios = [(1.0, pos_long), (-1.0, pos_short)]
            
        except Exception:
            # Syntax error or invalid operator combination
            return -10.0, 1.0, {}
            
        for direction, pos_series in scenarios:
            try:
                strategy = PrecalcStrategy(pos_series)
                result = self.backtest_engine.run(strategy, self.df_search)
                metrics = compute_metrics(result)
                
                calmar = metrics.get('calmar_ratio', 0.0)
                if calmar is None or np.isnan(calmar):
                    calmar = 0.0
                    
                total_trades = metrics.get('total_trades', 0)
                if total_trades < 15 or calmar < 1.1:
                    reward = -10.0
                else:
                    max_corr = 0.0
                    if self.global_position_matrix is not None and not self.global_position_matrix.empty:
                        pos_s = pos_series._data if hasattr(pos_series, '_data') else pos_series
                        common_idx = pos_s.index.intersection(self.global_position_matrix.index)
                        if len(common_idx) > 20:
                            # Align and forward fill inside corrwith if needed, but indices should match
                            corrs = self.global_position_matrix.loc[common_idx].corrwith(pos_s.loc[common_idx])
                            max_corr = corrs.abs().max()
                            if np.isnan(max_corr):
                                max_corr = 0.0
                                
                    s_calmar = min(1.0, max(0.0, (calmar - 1.1) / (REWARD_WEIGHTS['max_calmar'] - 1.1)))
                    s_ic = min(1.0, abs(rank_ic) / REWARD_WEIGHTS['max_ic'])
                    s_corr = max(0.0, 1.0 - max_corr)
                    
                    reward = (REWARD_WEIGHTS['calmar_weight'] * s_calmar + REWARD_WEIGHTS['ic_weight'] * s_ic) * s_corr
                    
                if reward > best_reward:
                    best_reward = reward
                    best_direction = direction
                    best_metrics = metrics
                    best_metrics['rank_ic'] = rank_ic
                    best_metrics['window'] = window
                    best_metrics['z_score_threshold'] = z_score_thresh
            except Exception:
                pass
                
        if len(self.cache) > self.max_cache_size:
            # Evict the oldest 50% of cache entries (FIFO based on insertion order)
            keys = list(self.cache.keys())
            for k in keys[:len(keys) // 2]:
                self.cache.pop(k, None)
            
        self.cache[cache_key] = (best_reward, best_direction, best_metrics)
        return best_reward, best_direction, best_metrics

    def run_search_from_blueprint(self, root_ast: ASTNode, n_iterations: int = 100):
        """
        Run MCTS to expand an AST tree blueprint into trading strategies.
        
        This search follows the Unified Compiler Architecture:
        1. Wraps the root AST in a `strategy_root` node containing placeholders
           for `window` and `z_score`.
        2. Performs MCTS iterations. In each iteration:
           - Selection: Navigates the tree to find the best child according to UCT.
           - Expansion: Adds a new node by choosing an untried expansion action.
           - Simulation: Performs a random rollout from the new state to a terminal state.
           - Evaluation: Runs a backtest to evaluate the terminal state and checks FSA cache.
           - Backpropagation: Propagates the max reward (risk-seeking) back up the path.
        3. Monitors Shannon Entropy of root node for early convergence stopping.
        4. Updates the leaderboard with successful candidates.
        
        Parameters
        ----------
        root_ast : ASTNode
            The parsed AST blueprint from LLM JSON to start searching from.
        n_iterations : int, default 100
            Number of MCTS iterations to execute.
        """
        # Wrap root_ast to enable MCTS to discover window and z_score parameters
        window_node = ASTNode(name="window", value="?")
        z_node = ASTNode(name="z_score", value="?")
        new_root = ASTNode(name="strategy_root", children=[window_node, z_node, root_ast])
        
        root_state = MCTSState(new_root, self.max_depth)
        root_node = MCTSNode(root_state)
        
        print(f"[MCTS] Starting unified search from Blueprint | Depth: {self.max_depth} | Iterations: {n_iterations}")
        
        start_time = time.time()
        for i in range(1, n_iterations + 1):
            if i % 10 == 0:
                elapsed = time.time() - start_time
                print(f"  [MCTS] Iteration {i}/{n_iterations} | Cache size: {len(self.cache)} | Best reward: {max([x['reward'] for x in self.leaderboard]) if self.leaderboard else 'N/A'} | Elapsed: {elapsed:.1f}s")
                
            # Entropy Convergence Check
            if i >= REWARD_WEIGHTS['burn_in'] and i % 500 == 0:
                total_visits = root_node.visit_count
                valid_children = [c for c in root_node.children if c.visit_count > 0]
                k = len(valid_children)
                if k >= 2:
                    entropy = 0.0
                    for child in valid_children:
                        p_i = child.visit_count / total_visits
                        if p_i > 0:
                            entropy -= p_i * math.log2(p_i)
                    normalized_entropy = entropy / math.log2(k)
                    if normalized_entropy < REWARD_WEIGHTS['entropy_threshold']:
                        print(f"\n[MCTS] Hội tụ Toán học tại vòng {i}!")
                        print(f"[MCTS] Normalized Entropy: {normalized_entropy:.4f} < {REWARD_WEIGHTS['entropy_threshold']}")
                        break
                        
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
                if terminal_state.ast_tree.name == "strategy_root":
                    expr_code = ast_to_code(terminal_state.ast_tree.children[2])
                    window = terminal_state.ast_tree.children[0].value
                    z_score = terminal_state.ast_tree.children[1].value
                else:
                    expr_code = ast_to_code(terminal_state.ast_tree)
                    window = 20
                    z_score = 1.0
                    
                self.update_leaderboard(expr_code, reward, direction, metrics, window, z_score)
                
                # Update FSA Rolling Window Cache if good reward
                if reward > 1.0:
                    cache_key = f"{expr_code}_{window}_{z_score}"
                    self.add_to_fsa_cache(cache_key)
                
            # Risk-Seeking Backpropagation (Tail Quantile)
            for p_node in path:
                p_node.visit_count += 1
                if reward > p_node.max_reward:
                    p_node.max_reward = reward

        print(f"[MCTS] Search completed in {time.time() - start_time:.1f}s.")

    def select_best_child(self, node: MCTSNode) -> MCTSNode:
        """
        Select a child node that maximizes the Upper Confidence Bound for Trees (UCT).
        
        This implements a risk-seeking (Tail Quantile) optimization by using 
        the maximum reward (`max_reward`) of the child node as the exploitation term 
        instead of the average reward.
        
        Parameters
        ----------
        node : MCTSNode
            The parent node.
            
        Returns
        -------
        MCTSNode
            The selected child node.
        """
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
        """
        Perform a random simulation (rollout) from the given MCTS state.
        
        Expands the state randomly by choosing a random action from all
        available actions until a terminal state is reached.
        
        Parameters
        ----------
        state : MCTSState
            The state to start the rollout from.
            
        Returns
        -------
        MCTSState
            A terminal state resulting from the random simulation.
        """
        curr_state = state
        while not curr_state.is_terminal():
            actions = curr_state.get_actions()
            if not actions:
                break
            action = random.choice(actions)
            curr_state = curr_state.apply_action(action)
        return curr_state

    def update_leaderboard(self, expr_str: str, reward: float, direction: float, metrics: dict, window: int = 20, z_score: float = 1.0):
        """
        Update the rolling leaderboard cache with a newly evaluated candidate.
        
        Prevents duplicates by checking if the exact expression with the same
        window and z-score is already present. The leaderboard is sorted in 
        descending order of reward and capped at 100 candidates.
        
        Parameters
        ----------
        expr_str : str
            The code string of the discovered alpha expression.
        reward : float
            The reward value computed for the candidate.
        direction : float
            The trading direction (1.0 or -1.0).
        metrics : dict
            The strategy's performance metrics.
        window : int, default 20
            The lookback window size.
        z_score : float, default 1.0
            The z-score entry threshold.
        """
        for item in self.leaderboard:
            if item['expr'] == expr_str and item.get('window') == window and item.get('z_score') == z_score:
                return
        
        self.leaderboard.append({
            'expr': expr_str,
            'reward': reward,
            'direction': direction,
            'window': window,
            'z_score': z_score,
            'metrics': metrics
        })
        self.leaderboard.sort(key=lambda x: x['reward'], reverse=True)
        self.leaderboard = self.leaderboard[:100] # Rolling Window Cache bounds

    def get_best_candidates(self) -> List[Dict[str, Any]]:
        return self.leaderboard
