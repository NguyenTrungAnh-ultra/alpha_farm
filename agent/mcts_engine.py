# MCTS Engine for Alpha Discovery
# Implements Monte Carlo Tree Search on Expression Trees to find profitable
# trading formulas under strict dimensional consistency rules.

import os
import sys
import math
import random
import time
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

PROJECT_ROOT = "f:/Projects/alpha_farm"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from xno_sdk.engine import SimpleAlgorithm
from backtest.engine import XNOBacktestEngine, load_data
from backtest.reporting import compute_metrics
from agent.mcts_dimensions import Dimension
from agent.portfolio import PortfolioManager

PERIODS = [5, 10, 14, 20, 30, 60]

class ASTNode:
    """Represents a node in the expression tree (AST)."""
    def __init__(self, node_type: str, name: str, children: Optional[List['ASTNode']] = None, value: Any = None, req_dim: Optional[Dimension] = None):
        self.node_type = node_type  # 'placeholder', 'feature', 'constant', 'operator'
        self.name = name            # '?', 'close', 'sma', 'add', etc.
        self.children = children or []
        self.value = value          # for constant nodes
        self.req_dim = req_dim      # for placeholders

    def clone(self) -> 'ASTNode':
        cloned_children = [child.clone() for child in self.children]
        return ASTNode(
            node_type=self.node_type,
            name=self.name,
            children=cloned_children,
            value=self.value,
            req_dim=self.req_dim
        )

    def to_code(self) -> str:
        """Translates the AST node and its children to Python code string."""
        if self.node_type == 'placeholder':
            return '?'
            
        elif self.node_type == 'feature':
            feature_mapping = {
                'close': 'close',
                'open': 'open_',
                'high': 'high',
                'low': 'low',
                'volume': 'volume',
                'vn30_close': 'self.data.pv_vn30_close'
            }
            return feature_mapping.get(self.name, self.name)
            
        elif self.node_type == 'constant':
            return str(self.value)
            
        elif self.node_type == 'operator':
            # Mathematical operators
            if self.name == 'add':
                return f"({self.children[0].to_code()} + {self.children[1].to_code()})"
            elif self.name == 'sub':
                return f"({self.children[0].to_code()} - {self.children[1].to_code()})"
            elif self.name == 'mul':
                return f"({self.children[0].to_code()} * {self.children[1].to_code()})"
            elif self.name == 'div':
                return f"({self.children[0].to_code()} / ({self.children[1].to_code()} + 1e-8))"
                
            # Overlap operators & rolling functions
            elif self.name in ['sma', 'ema', 'wma', 'dema', 'tema', 'kama', 'rolling_mean', 'rolling_max', 'rolling_min', 'rolling_sum', 'rolling_std', 'stddev']:
                func = self.name
                series = self.children[0].to_code()
                period = self.children[1].to_code()
                if func in ['rolling_mean', 'rolling_max', 'rolling_min', 'rolling_sum', 'rolling_std']:
                    return f"self.feat.{func}({series}, window={period})"
                else:
                    return f"self.feat.{func}({series}, timeperiod={period})"
                    
            # Momentum / Oscillators
            elif self.name in ['rsi', 'roc', 'cmo', 'price_z', 'volume_z', 'zscore', 'rolling_rank', 'rolling_zscore']:
                series = self.children[0].to_code()
                period = self.children[1].to_code()
                if self.name in ['rolling_rank', 'rolling_zscore']:
                    return f"self.feat.{self.name}({series}, window={period})"
                else:
                    return f"self.feat.{self.name}({series}, timeperiod={period})"
                    
            elif self.name in ['cci', 'willr', 'natr']:
                period = self.children[0].to_code()
                return f"self.feat.{self.name}(high, low, close, timeperiod={period})"
                
            elif self.name == 'mfi':
                period = self.children[0].to_code()
                return f"self.feat.mfi(high, low, close, volume, timeperiod={period})"
                
            elif self.name == 'obv':
                return "self.feat.obv(close, volume)"
                
            elif self.name == 'atr':
                period = self.children[0].to_code()
                return f"self.feat.atr(high, low, close, timeperiod={period})"
                
        raise ValueError(f"Invalid node: {self.node_type}, {self.name}")

    def __repr__(self) -> str:
        return self.to_code()

def find_first_placeholder(node: ASTNode) -> Optional[ASTNode]:
    """Depth-first search to find the first placeholder node ('?')."""
    if node.node_type == 'placeholder':
        return node
    for child in node.children:
        ph = find_first_placeholder(child)
        if ph is not None:
            return ph
    return None

def get_node_depth(root: ASTNode, target: ASTNode, current_depth: int = 0) -> Optional[int]:
    """Calculates the depth of the target node in the root tree."""
    if root is target:
        return current_depth
    for child in root.children:
        d = get_node_depth(child, target, current_depth + 1)
        if d is not None:
            return d
    return None

# Action Space Definition
def get_terminals_for_dimension(dim: Dimension) -> List[ASTNode]:
    """Returns possible leaf expansions for a given dimension."""
    if dim == Dimension.CURRENCY:
        return [
            ASTNode('feature', 'close'),
            ASTNode('feature', 'open'),
            ASTNode('feature', 'high'),
            ASTNode('feature', 'low')
        ]
    elif dim == Dimension.VOLUME:
        return [
            ASTNode('feature', 'volume')
        ]
    elif dim == Dimension.RATIO:
        return [
            ASTNode('constant', '', value=val)
            for val in [0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
        ]
    return []

def get_operators_for_dimension(dim: Dimension) -> List[ASTNode]:
    """Returns possible operator expansions (with placeholder children) for a given dimension."""
    ops = []
    
    # 1. Math operators
    ops.append(ASTNode('operator', 'add', [ASTNode('placeholder', '?', req_dim=dim), ASTNode('placeholder', '?', req_dim=dim)]))
    ops.append(ASTNode('operator', 'sub', [ASTNode('placeholder', '?', req_dim=dim), ASTNode('placeholder', '?', req_dim=dim)]))
    
    if dim == Dimension.CURRENCY:
        # mul: currency * ratio
        ops.append(ASTNode('operator', 'mul', [ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY), ASTNode('placeholder', '?', req_dim=Dimension.RATIO)]))
        # div: currency / ratio
        ops.append(ASTNode('operator', 'div', [ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY), ASTNode('placeholder', '?', req_dim=Dimension.RATIO)]))
        
        # Overlap Moving Averages: input must be CURRENCY, preserves CURRENCY
        for period in PERIODS:
            for ma in ['sma', 'ema', 'wma', 'dema', 'tema']:
                ops.append(ASTNode('operator', ma, [
                    ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY),
                    ASTNode('constant', '', value=period)
                ]))
                
        # Volatility: atr outputs price difference (CURRENCY)
        for period in PERIODS:
            ops.append(ASTNode('operator', 'atr', [ASTNode('constant', '', value=period)]))

    elif dim == Dimension.VOLUME:
        # mul: volume * ratio
        ops.append(ASTNode('operator', 'mul', [ASTNode('placeholder', '?', req_dim=Dimension.VOLUME), ASTNode('placeholder', '?', req_dim=Dimension.RATIO)]))
        # div: volume / ratio
        ops.append(ASTNode('operator', 'div', [ASTNode('placeholder', '?', req_dim=Dimension.VOLUME), ASTNode('placeholder', '?', req_dim=Dimension.RATIO)]))
        # obv: outputs VOLUME
        ops.append(ASTNode('operator', 'obv'))

    elif dim == Dimension.RATIO:
        # mul: ratio * ratio
        ops.append(ASTNode('operator', 'mul', [ASTNode('placeholder', '?', req_dim=Dimension.RATIO), ASTNode('placeholder', '?', req_dim=Dimension.RATIO)]))
        # div: currency/currency, volume/volume, or ratio/ratio
        ops.append(ASTNode('operator', 'div', [ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY), ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY)]))
        ops.append(ASTNode('operator', 'div', [ASTNode('placeholder', '?', req_dim=Dimension.VOLUME), ASTNode('placeholder', '?', req_dim=Dimension.VOLUME)]))
        ops.append(ASTNode('operator', 'div', [ASTNode('placeholder', '?', req_dim=Dimension.RATIO), ASTNode('placeholder', '?', req_dim=Dimension.RATIO)]))

        # Momentum & Oscillators: always return RATIO
        for period in PERIODS:
            # RSI, ROC, CMO of close price
            ops.append(ASTNode('operator', 'rsi', [ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY), ASTNode('constant', '', value=period)]))
            ops.append(ASTNode('operator', 'roc', [ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY), ASTNode('constant', '', value=period)]))
            ops.append(ASTNode('operator', 'cmo', [ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY), ASTNode('constant', '', value=period)]))
            
            # CCI, WILLR, MFI, NATR
            ops.append(ASTNode('operator', 'cci', [ASTNode('constant', '', value=period)]))
            ops.append(ASTNode('operator', 'willr', [ASTNode('constant', '', value=period)]))
            ops.append(ASTNode('operator', 'mfi', [ASTNode('constant', '', value=period)]))
            ops.append(ASTNode('operator', 'natr', [ASTNode('constant', '', value=period)]))
            
            # Zscore functions
            ops.append(ASTNode('operator', 'price_z', [ASTNode('feature', 'close'), ASTNode('constant', '', value=period)]))
            ops.append(ASTNode('operator', 'volume_z', [ASTNode('feature', 'volume'), ASTNode('constant', '', value=period)]))
            
            # Rolling Rank/Zscore of currency
            ops.append(ASTNode('operator', 'rolling_rank', [ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY), ASTNode('constant', '', value=period)]))
            ops.append(ASTNode('operator', 'rolling_zscore', [ASTNode('placeholder', '?', req_dim=Dimension.CURRENCY), ASTNode('constant', '', value=period)]))

    return ops

class MCTSState:
    """Represents a search tree state (a complete or partial AST)."""
    def __init__(self, ast_tree: ASTNode, max_depth: int = 3):
        self.ast_tree = ast_tree
        self.max_depth = max_depth

    def is_terminal(self) -> bool:
        return find_first_placeholder(self.ast_tree) is None

    def get_actions(self) -> List[ASTNode]:
        ph = find_first_placeholder(self.ast_tree)
        if ph is None:
            return []
        
        depth = get_node_depth(self.ast_tree, ph)
        # If at max depth, only allow leaf terminal expansions
        if depth is not None and depth >= self.max_depth:
            return get_terminals_for_dimension(ph.req_dim)
        
        # Otherwise, allow both operators and terminals
        return get_terminals_for_dimension(ph.req_dim) + get_operators_for_dimension(ph.req_dim)

    def apply_action(self, action_node: ASTNode) -> 'MCTSState':
        new_tree = self.ast_tree.clone()
        ph = find_first_placeholder(new_tree)
        if ph is not None:
            ph.node_type = action_node.node_type
            ph.name = action_node.name
            ph.children = [child.clone() for child in action_node.children]
            ph.value = action_node.value
            ph.req_dim = action_node.req_dim
        return MCTSState(new_tree, self.max_depth)

class MCTSNode:
    """Represents a node in the MCTS tree structure (containing state and stats)."""
    def __init__(self, state: MCTSState, parent: Optional['MCTSNode'] = None, action_leading_here: Optional[ASTNode] = None):
        self.state = state
        self.parent = parent
        self.action_leading_here = action_leading_here
        self.children: List['MCTSNode'] = []
        self.visit_count = 0
        self.total_reward = 0.0
        self.untried_actions = state.get_actions()

    def is_fully_expanded(self) -> bool:
        return len(self.untried_actions) == 0

    def is_leaf(self) -> bool:
        return len(self.children) == 0

class DynamicMCTSStrategy(SimpleAlgorithm):
    """Memory-efficient strategy container for running dynamically generated formulas."""
    _emulator_source_code = "class CustomStrategy(SimpleAlgorithm):\n    def __algorithm__(self):\n        pass"
    position_scale = 0.2  # Default scale for search

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
            # Fallback to zero series
            self.alpha_series = close * 0.0
            alpha_val = close * 0.0

        # Normalize to [-1.0, 1.0]
        window = 20  # Cửa sổ ngắn 20 phiên để bám sát vi mô
        r_mean = self.feat.rolling_mean(alpha_val, window)
        r_std = self.feat.rolling_std(alpha_val, window) + 1e-8
        
        z_score = (alpha_val - r_mean) / r_std
        z_score = z_score * direction

        # Cắt ngưỡng: Vào lệnh khi độ lệch chuẩn phá vỡ mức 1.0 (1 Sigma)
        raw_pos = self.op.where(z_score > 1.0, pos_scale, self.op.where(z_score < -1.0, -pos_scale, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == pos_scale
        short_mask = raw_pos == -pos_scale
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position=pos_scale)
        self.set_positions(short_mask, position=-pos_scale)


class MCTSEngine:
    def __init__(self, timeframe: str = '10m', max_depth: int = 3, exploration_c: float = 1.414):
        self.timeframe = timeframe
        self.max_depth = max_depth
        self.exploration_c = exploration_c
        
        # Load backtest data
        print(f"[MCTS] Loading data for {timeframe}...")
        self.df = load_data(timeframe)
        self.df['Volume'] = self.df['Volume'].fillna(0.0)
        
        # For fast search, we evaluate on a 2-year window (2023-2025)
        # Once found, we backtest on full 5 years
        # TWEAK: For absolute accuracy (but massive CPU cost), comment out the slice below 
        # to force MCTS to evaluate rewards using the full 5-year history.
        # self.df_search = self.df  <-- Use this for max power
        self.df_search = self.df['2023-01-01':]
        if len(self.df_search) < 100:
            self.df_search = self.df
            
        self.backtest_engine = XNOBacktestEngine()
        self.portfolio_manager = PortfolioManager()
        
        # Cache to store evaluated formulas
        # Key: expr_str, Value: (reward, direction, metrics)
        self.cache: Dict[str, tuple] = {}
        
        # Leaderboard of top complete AST formulas
        self.leaderboard: List[Dict[str, Any]] = []

    def compute_rank_ic(self, alpha_series: pd.Series, close_series: pd.Series) -> float:
        fwd_returns = close_series.pct_change(1).shift(-1)
        valid = pd.DataFrame({'alpha': alpha_series, 'fwd_ret': fwd_returns}).dropna()
        if len(valid) < 20:
            return 0.0
        return valid['alpha'].corr(valid['fwd_ret'], method='spearman')

    def evaluate_expression(self, expr_str: str) -> tuple:
        """Evaluates an expression and returns (reward, direction, metrics)."""
        if expr_str in self.cache:
            return self.cache[expr_str]
            
        # We test both positive and negative directions to see which has positive Sharpe
        best_reward = -10.0
        best_direction = 1.0
        best_metrics = {}
        
        for direction in [1.0, -1.0]:
            try:
                strategy = DynamicMCTSStrategy(expr_str=expr_str, direction=direction)
                result = self.backtest_engine.run(strategy, self.df_search)
                metrics = compute_metrics(result)
                
                # Check RankIC
                raw_alpha = strategy.alpha_series._data if hasattr(strategy.alpha_series, '_data') else strategy.alpha_series
                rank_ic = self.compute_rank_ic(raw_alpha, self.df_search['Close'])
                
                sharpe = metrics.get('sharpe_ratio', 0.0)
                if np.isnan(sharpe):
                    sharpe = 0.0
                    
                # Correlation penalty (against existing alphas in portfolio)
                # MỚI
                eq_curve = result.equity_curve
                max_corr = 0.0
                
                # So sánh trực tiếp với các đường cong vốn đã lọt vào Leaderboard
                if self.leaderboard:
                    correlations = []
                    for item in self.leaderboard:
                        hist_curve = item['metrics'].get('equity_curve_series')
                        if hist_curve is not None:
                            # Tính tương quan Spearman hoặc Pearson
                            valid_df = pd.DataFrame({'curr': eq_curve, 'hist': hist_curve}).dropna()
                            if len(valid_df) > 20 and valid_df['curr'].std() > 0 and valid_df['hist'].std() > 0:
                                corr = valid_df['curr'].corr(valid_df['hist'])
                                correlations.append(corr)
                    if correlations:
                        max_corr = max(correlations)
                
                # Minimum trades check
                total_trades = metrics.get('total_trades', 0)
                if total_trades < 15:
                    reward = 0.0
                else:
                    # Reward function: combination of RankIC and Sharpe, with correlation penalty
                    reward = 10.0 * abs(rank_ic) + max(0.0, sharpe) - 5.0 * max_corr
                    
                if reward > best_reward:
                    best_reward = reward
                    best_direction = direction
                    best_metrics = metrics
                    best_metrics['rank_ic'] = rank_ic
                    best_metrics['max_corr'] = max_corr
            except Exception as e:
                # If crash, reward is very negative
                pass
                
        self.cache[expr_str] = (best_reward, best_direction, best_metrics)
        return best_reward, best_direction, best_metrics

    def run_search(self, root_dim: Dimension, n_iterations: int = 100):
        """Runs the MCTS search starting with a placeholder root of root_dim."""
        root_ast = ASTNode('placeholder', '?', req_dim=root_dim)
        root_state = MCTSState(root_ast, self.max_depth)
        root_node = MCTSNode(root_state)
        
        print(f"[MCTS] Starting search for root dimension: {root_dim.name} | Depth: {self.max_depth} | Iterations: {n_iterations}")
        
        start_time = time.time()
        for i in range(1, n_iterations + 1):
            if i % 10 == 0:
                elapsed = time.time() - start_time
                print(f"  [MCTS] Iteration {i}/{n_iterations} | Cache size: {len(self.cache)} | Best reward: {max([x['reward'] for x in self.leaderboard]) if self.leaderboard else 'N/A'} | Elapsed: {elapsed:.1f}s")
                
            # 1. Selection
            node = root_node
            path = [node]
            while node.is_fully_expanded() and not node.is_leaf():
                node = self.select_best_child(node)
                path.append(node)
                
            # 2. Expansion
            if not node.state.is_terminal():
                if not node.is_fully_expanded():
                    action = node.untried_actions.pop(random.randrange(len(node.untried_actions)))
                    new_state = node.state.apply_action(action)
                    child_node = MCTSNode(new_state, parent=node, action_leading_here=action)
                    node.children.append(child_node)
                    node = child_node
                    path.append(node)
                    
            # 3. Rollout / Simulation
            terminal_state = self.rollout(node.state)
            
            # 4. Evaluation
            expr_code = terminal_state.ast_tree.to_code()
            reward, direction, metrics = self.evaluate_expression(expr_code)
            
            # Update Leaderboard
            if terminal_state.is_terminal():
                self.update_leaderboard(expr_code, reward, direction, metrics)
                
            # 5. Backpropagation
            for p_node in path:
                p_node.visit_count += 1
                p_node.total_reward += reward

        print(f"[MCTS] Search completed in {time.time() - start_time:.1f}s.")

    def select_best_child(self, node: MCTSNode) -> MCTSNode:
        """Selects child that maximizes UCT value."""
        best_uct = -1e9
        best_child = None
        
        log_parent_visits = math.log(node.visit_count)
        
        for child in node.children:
            if child.visit_count == 0:
                uct = 1e9  # prioritize unvisited nodes
            else:
                mean_reward = child.total_reward / child.visit_count
                exploration = self.exploration_c * math.sqrt(log_parent_visits / child.visit_count)
                uct = mean_reward + exploration
                
            if uct > best_uct:
                best_uct = uct
                best_child = child
                
        return best_child or random.choice(node.children)

    def rollout(self, state: MCTSState) -> MCTSState:
        """Performs a random rollout until the state is terminal (no placeholders)."""
        curr_state = state
        while not curr_state.is_terminal():
            actions = curr_state.get_actions()
            if not actions:
                break
            # Prefer leaf terminal expansions during rollout if tree is getting deep
            # to avoid infinite/extremely deep trees
            action = random.choice(actions)
            curr_state = curr_state.apply_action(action)
        return curr_state

    def update_leaderboard(self, expr_str: str, reward: float, direction: float, metrics: dict):
        """Adds a complete candidate formula to the leaderboard."""
        # Check if already present
        for item in self.leaderboard:
            if item['expr'] == expr_str:
                return
                
        # Count parameters
        # Parameters are constant nodes
        # Simple count of numbers in string or parsing
        # Let's count timeperiod parameters and other constants in the expression
        import re
        periods = re.findall(r"timeperiod=\d+|window=\d+", expr_str)
        consts = re.findall(r"\b\d+\.\d+|\b\d+\b", expr_str)
        # Avoid double-counting numbers in timeperiod/window
        param_count = len(periods) + len([c for c in consts if not any(p.endswith(c) for p in periods)])
        
        self.leaderboard.append({
            'expr': expr_str,
            'reward': reward,
            'direction': direction,
            'metrics': metrics,
            'param_count': param_count
        })
        # Sort by reward descending
        self.leaderboard.sort(key=lambda x: x['reward'], reverse=True)
        # Limit to top 20
        self.leaderboard = self.leaderboard[:20]

    def get_best_candidates(self) -> List[Dict[str, Any]]:
        return self.leaderboard

if __name__ == "__main__":
    # Test script entry point
    engine = MCTSEngine(timeframe='10m', max_depth=3)
    engine.run_search(Dimension.RATIO, n_iterations=30)
    print("\nBest candidates discovered:")
    for i, c in enumerate(engine.get_best_candidates()[:5], 1):
        print(f"[{i}] Expr: {c['expr']}")
        print(f"    Reward: {c['reward']:.4f} | Direction: {c['direction']} | Sharpe: {c['metrics'].get('sharpe_ratio'):.4f} | RankIC: {c['metrics'].get('rank_ic'):.4f}")
