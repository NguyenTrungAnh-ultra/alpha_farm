import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# MCTS Engine for Alpha Discovery - Unified Compiler Architecture
import math
import random
import time
import logging
from collections import Counter
import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from typing import List, Dict, Any, Optional, Callable

from core_engine.AlphaEngine import AlphaStrategy, AlphaDataProxy
from core_engine.AlphaPrimitives import ts_mean, ts_sum, ts_max, ts_min, ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
from core_engine.BacktestEngine import AlphaBacktestEngine, load_data
from core_engine.CalculateMetrics import compute_metrics
from strategy_workflows.MCTSDimensions import (
    Dimension, OPERATOR_REGISTRY, DATA_FIELD_DIMENSIONS, OperatorGroup, UNIMPLEMENTED_OPERATORS,
    BOOLEAN_DIMS, NUMERIC_DIMS, UNBOUNDED_DEPTH, analyze_dimensions, operators_for_slot,
)
from strategy_workflows.PortfolioManager import PortfolioManager
from strategy_workflows.SemanticCompiler import ASTNode
from utilities.AppConfig import (
    REWARD_WEIGHTS, BASE_PERIODS, BASE_WINDOW_SEARCH,
    BASELINE_TF_MINUTES, TIMEFRAME_MINUTES, MCTS_QUALITY_THRESHOLDS,
    MIN_TRADES, REWARD_MODE, REWARD_MODES, MCTS_MAX_DEPTH
)

logger = logging.getLogger(__name__)

# Functions visible to generated expressions. Exported strategy files import the same names.
TS_FUNCTIONS = {
    'ts_mean': ts_mean, 'ts_sum': ts_sum, 'ts_max': ts_max, 'ts_min': ts_min,
    'ts_rank': ts_rank, 'ts_corr': ts_corr, 'ts_zscore': ts_zscore,
    'ts_argmax': ts_argmax, 'ts_argmin': ts_argmin,
}

# Data field -> variable name inside generated code. Fields without an entry (pv_vn30_close)
# are not provided by the OHLCV data and are never proposed or rendered.
FIELD_EXPRESSIONS = {
    'pv_open': 'open_',
    'pv_high': 'high',
    'pv_low': 'low',
    'pv_close': 'close',
    'pv_volume': 'volume',
}

NODE_WITH_VALUE_SLOT = ('window', 'z_score', 'threshold_upper', 'threshold_lower')


def scaled_ladders(timeframe: str) -> tuple:
    """(rolling-window choices, z-score-window choices) of a timeframe: the 10m baselines scaled by bar length."""
    scale = BASELINE_TF_MINUTES / TIMEFRAME_MINUTES.get(timeframe, 10)
    periods = sorted(set(max(2, round(p * scale)) for p in BASE_PERIODS))
    windows = sorted(set(max(2, round(w * scale)) for w in BASE_WINDOW_SEARCH))
    return periods, windows


def _sample_std(values: np.ndarray) -> float:
    """Sample standard deviation (ddof=1) with the arithmetic of `pandas.Series.std`, so a constant input gives exactly the same 0 test."""
    mean = values.sum(dtype=np.float64) / len(values)
    return np.sqrt(((mean - values) ** 2).sum(dtype=np.float64) / (len(values) - 1))


def needs_window(node: ASTNode) -> bool:
    """True for a TIME_SERIES operator whose rolling window has not been chosen yet."""
    meta = OPERATOR_REGISTRY.get(node.name)
    return meta is not None and meta["group"] == OperatorGroup.TIME_SERIES and node.window is None


def is_implemented(op_name: str) -> bool:
    return op_name in OPERATOR_REGISTRY and op_name not in UNIMPLEMENTED_OPERATORS


def find_unimplemented_operator(node: ASTNode) -> Optional[str]:
    """Return the first operator in the tree that has no code generation, or None."""
    if node.name in UNIMPLEMENTED_OPERATORS:
        return node.name
    for child in node.children:
        found = find_unimplemented_operator(child)
        if found is not None:
            return found
    return None


def ast_to_code(node: ASTNode) -> str:
    """
    Translate an AST node and its children to a Python expression string.

    Rendering is a pure function of the tree: every TIME_SERIES window is read from
    `node.window`, which the search fixes when the node is expanded.
    """
    if node.name == "?":
        return '?'

    if node.name in ["Constant", "z_score", "window"]:
        return str(node.value)

    if node.name in DATA_FIELD_DIMENSIONS:
        if node.name not in FIELD_EXPRESSIONS:
            raise ValueError(f"Data field {node.name} is not provided by the OHLCV data")
        return FIELD_EXPRESSIONS[node.name]

    if node.name not in OPERATOR_REGISTRY:
        raise ValueError(f"Unknown operator: {node.name}")
    if node.name in UNIMPLEMENTED_OPERATORS:
        raise ValueError(f"Operator {node.name} has no code generation")

    group = OPERATOR_REGISTRY[node.name]["group"]

    if group == OperatorGroup.TIME_SERIES:
        if node.window is None:
            raise ValueError(f"{node.name} has no window")
        # Extra Constant children (e.g. a window the LLM wrote) are not data arguments.
        arity = len(OPERATOR_REGISTRY[node.name]["input_dims"])
        series = [c for c in node.children if c.name != "Constant"]
        data_nodes = series if len(series) == arity else node.children[:arity]
        data_args = [ast_to_code(c) for c in data_nodes]
        return f"{node.name}({', '.join(data_args)}, {node.window})"

    args = [ast_to_code(c) for c in node.children]

    if group == OperatorGroup.STATISTICS:
        if node.name == 'div':
            return f"({args[0]} / ({args[1]} + 1e-8))"
        op_map = {'add': '+', 'sub': '-', 'mult': '*'}
        return f"({args[0]} {op_map[node.name]} {args[1]})"

    if group == OperatorGroup.LOGIC:
        if node.name == 'not_':
            return f"(~{args[0]})"
        op_map = {'and_': '&', 'or_': '|', 'greater_than': '>', 'less_than': '<', 'equal': '=='}
        return f"({args[0]} {op_map[node.name]} {args[1]})"

    return f"{node.name}({', '.join(args)})"


def build_namespace(data: AlphaDataProxy) -> dict:
    """Variables and functions that generated expressions are evaluated against."""
    ns = {
        'open_': data.pv_open, 'high': data.pv_high, 'low': data.pv_low,
        'close': data.pv_close, 'volume': data.pv_volume,
    }
    ns.update(TS_FUNCTIONS)
    return ns


def evaluate_alpha(expr_str: str, data: AlphaDataProxy) -> pd.Series:
    """Evaluate a generated expression to a Series aligned with the data index."""
    alpha = eval(expr_str, {"__builtins__": {}}, build_namespace(data))
    if not isinstance(alpha, pd.Series):
        raise TypeError(f"Expression produced {type(alpha).__name__}, expected a Series: {expr_str}")
    return alpha


def compute_positions(
    template: str,
    alpha: pd.Series,
    direction: float,
    position_scale: float,
    window: int = 20,
    z_score_threshold: float = 1.0,
    threshold_upper: float = 70.0,
    threshold_lower: float = 30.0,
) -> pd.Series:
    """
    Turn an alpha series into target positions (+scale / -scale / 0), aligned with alpha.index.

    NORMALIZED: rolling z-score of alpha against +-threshold; RATIO: alpha against upper/lower
    thresholds; BOOLEAN: long where alpha is True, short elsewhere. NaN never triggers a signal.
    `direction` -1 mirrors the signal.
    """
    if template == "NORMALIZED":
        z = ts_zscore(alpha, window) * direction
        long_cond = z > z_score_threshold
        short_cond = z < -z_score_threshold
    elif template == "RATIO":
        above = alpha > threshold_upper
        below = alpha < threshold_lower
        long_cond, short_cond = (above, below) if direction == 1.0 else (below, above)
    elif template == "BOOLEAN":
        truth = alpha.astype(bool)
        long_cond, short_cond = (truth, ~truth) if direction == 1.0 else (~truth, truth)
    else:
        raise ValueError(f"Unknown template: {template}")
    positions = np.where(long_cond, position_scale, np.where(short_cond, -position_scale, 0.0))
    return pd.Series(positions, index=alpha.index, dtype=np.float64)


def describe_candidate(ast_tree: ASTNode) -> Dict[str, Any]:
    """Render a terminal tree into its template, expression and parameters (no randomness)."""
    desc = {
        'window': 20, 'z_score_threshold': 1.0,
        'threshold_upper': 70.0, 'threshold_lower': 30.0,
    }
    if ast_tree.name == "normalized_template":
        desc['template'] = "NORMALIZED"
        desc['expr'] = ast_to_code(ast_tree.children[0])
        desc['window'] = ast_tree.children[1].value
        desc['z_score_threshold'] = ast_tree.children[2].value
        desc['cache_key'] = f"{desc['expr']}_norm_{desc['window']}_{desc['z_score_threshold']}"
    elif ast_tree.name == "ratio_template":
        desc['template'] = "RATIO"
        desc['expr'] = ast_to_code(ast_tree.children[0])
        desc['threshold_upper'] = ast_tree.children[1].value
        desc['threshold_lower'] = ast_tree.children[2].value
        desc['cache_key'] = f"{desc['expr']}_ratio_{desc['threshold_upper']}_{desc['threshold_lower']}"
    else:
        desc['template'] = "BOOLEAN"
        desc['expr'] = ast_to_code(ast_tree)
        desc['cache_key'] = f"{desc['expr']}_bool"
    return desc


def clone_ast(node: ASTNode) -> ASTNode:
    return ASTNode(
        name=node.name,
        children=[clone_ast(c) for c in node.children],
        value=node.value,
        window=node.window,
    )

def find_first_placeholder(node: ASTNode) -> Optional[ASTNode]:
    """
    Depth-first search (parent before children) for the next thing the search must decide:
    a '?' slot, a template parameter slot, or a TIME_SERIES node without a window.
    """
    if node.name == '?':
        return node
    if node.name in NODE_WITH_VALUE_SLOT and node.value == '?':
        return node
    if needs_window(node):
        return node
    for child in node.children:
        ph = find_first_placeholder(child)
        if ph is not None:
            return ph
    return None

def find_parent(root: ASTNode, target: ASTNode) -> Optional[ASTNode]:
    for child in root.children:
        if child is target:
            return root
        found = find_parent(child, target)
        if found is not None:
            return found
    return None

def required_dimensions(root: ASTNode, ph: ASTNode, max_depth: Optional[int] = None) -> frozenset:
    """
    Dimensions a '?' slot can take so the whole tree stays valid (empty if the tree is invalid).

    Sibling and ancestor dimensions constrain it, e.g. the slot in `sub(pv_close, ts_mean(?))`
    is CURRENCY only. `max_depth` limits what the slot can still grow into.
    """
    return analyze_dimensions(root, max_depth).slot_dims.get(id(ph), frozenset())

def get_node_depth(root: ASTNode, target: ASTNode, current_depth: int = 0) -> Optional[int]:
    if root is target:
        return current_depth
    for child in root.children:
        d = get_node_depth(child, target, current_depth + 1)
        if d is not None:
            return d
    return None

# MCTS Expansions
def terminals_for_dimensions(allowed, in_time_series: bool = False) -> List[ASTNode]:
    """Leaf expansions (data fields, constants) whose dimension is in `allowed`."""
    terminals = []
    if allowed == BOOLEAN_DIMS:
        # No leaf produces a BOOLEAN; a BOOLEAN slot always needs an operator.
        return terminals

    for field, field_dim in DATA_FIELD_DIMENSIONS.items():
        if field in FIELD_EXPRESSIONS and field_dim in allowed:
            terminals.append(ASTNode(name=field))

    # A rolling operator needs a series, not a scalar constant.
    if Dimension.RATIO in allowed and not in_time_series:
        for val in [0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]:
            terminals.append(ASTNode(name="Constant", value=val))

    return terminals

def operators_for_dimensions(allowed, remaining: int) -> List[ASTNode]:
    """
    Operator expansions (with `?` children, one per input) for a slot limited to `allowed`.

    `remaining` is the number of operator levels the slot may still use. An operator is offered
    only if some dimension of its inputs makes its output fall into `allowed`; its children are
    then constrained in turn when the search reaches them.
    """
    expect_boolean = allowed == BOOLEAN_DIMS
    return [
        ASTNode(name=op, children=[ASTNode(name='?') for _ in OPERATOR_REGISTRY[op]["input_dims"]])
        for op in operators_for_slot(allowed, remaining, expect_boolean)
    ]

def _dimensions_of(dim: Dimension) -> frozenset:
    if dim == Dimension.BOOLEAN:
        return BOOLEAN_DIMS
    return NUMERIC_DIMS if dim == Dimension.ANY else frozenset({dim})

def get_terminals_for_dimension(dim: Dimension) -> List[ASTNode]:
    """Leaf expansions for one dimension (ANY = every numeric dimension)."""
    return terminals_for_dimensions(_dimensions_of(dim))

def get_operators_for_dimension(dim: Dimension) -> List[ASTNode]:
    """Operator expansions for one dimension (ANY = every numeric dimension), with unlimited depth."""
    return operators_for_dimensions(_dimensions_of(dim), UNBOUNDED_DEPTH)

class MCTSState:
    """
    Represents a state in the Monte Carlo Tree Search.

    Note on Depth:
        `MCTSState` defaults to a `max_depth` of 3. However, when run from
        `MCTSEngine`, the engine's `max_depth` (which defaults to 4) is passed
        down and overrides this default value.
    """
    def __init__(self, ast_tree: ASTNode, max_depth: int = 3, scaled_window_search: list = None, scaled_periods: list = None):
        """
        Initialize the MCTSState.

        Parameters
        ----------
        ast_tree : ASTNode
            The current AST tree representing the formula.
        max_depth : int, default 3
            The maximum allowed depth for tree expansion. Typically overridden
            by MCTSEngine's max_depth (default 4).
        scaled_window_search : list, default None
            Dynamic list of window sizes for MCTS to search (template z-score window).
        scaled_periods : list, default None
            Window sizes MCTS chooses from for each TIME_SERIES operator.
        """
        self.ast_tree = ast_tree
        self.max_depth = max_depth
        self.scaled_window_search = scaled_window_search or [5, 10, 14, 20, 30, 40, 60]
        self.scaled_periods = scaled_periods or [5, 10, 14, 20, 30, 60]

    def is_terminal(self) -> bool:
        return find_first_placeholder(self.ast_tree) is None

    def get_actions(self) -> List[ASTNode]:
        ph = find_first_placeholder(self.ast_tree)
        if ph is None:
            return []

        if needs_window(ph):
            return [ASTNode(name=ph.name, window=w) for w in self.scaled_periods]
        if ph.name == 'window':
            return [ASTNode(name='window', value=v) for v in self.scaled_window_search]
        if ph.name == 'z_score':
            return [ASTNode(name='z_score', value=v) for v in [0.5, 1.0, 1.5, 2.0, 2.5]]
        if ph.name == 'threshold_upper':
            return [ASTNode(name='threshold_upper', value=v) for v in [60.0, 65.0, 70.0, 75.0, 80.0]]
        if ph.name == 'threshold_lower':
            return [ASTNode(name='threshold_lower', value=v) for v in [20.0, 25.0, 30.0, 35.0, 40.0]]

        allowed = required_dimensions(self.ast_tree, ph, self.max_depth)
        if not allowed:
            return []

        parent = find_parent(self.ast_tree, ph)
        in_time_series = parent is not None and parent.name in OPERATOR_REGISTRY \
            and OPERATOR_REGISTRY[parent.name]["group"] == OperatorGroup.TIME_SERIES

        # Past the depth limit only a BOOLEAN slot still takes an operator (a comparison whose
        # operands are then forced to be leaves), because no leaf is BOOLEAN.
        depth = get_node_depth(self.ast_tree, ph) or 0
        return terminals_for_dimensions(allowed, in_time_series) + \
            operators_for_dimensions(allowed, self.max_depth - depth)

    def apply_action(self, action_node: ASTNode) -> 'MCTSState':
        new_tree = clone_ast(self.ast_tree)
        ph = find_first_placeholder(new_tree)
        if ph is not None:
            if needs_window(ph):
                ph.window = action_node.window
            elif ph.name in NODE_WITH_VALUE_SLOT:
                ph.value = action_node.value
            else:
                ph.name = action_node.name
                ph.children = [clone_ast(child) for child in action_node.children]
                ph.value = action_node.value
                ph.window = action_node.window
        return MCTSState(new_tree, self.max_depth, self.scaled_window_search, self.scaled_periods)

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

class _TemplateStrategy(AlphaStrategy):
    """Replays a discovered formula: evaluates `expr_str` and applies `compute_positions`."""
    template = "NORMALIZED"
    expr_str = ""
    direction = 1.0
    position_scale = 0.2
    window = 20
    z_score_threshold = 1.0
    threshold_upper = 70.0
    threshold_lower = 30.0

    def __algorithm__(self):
        alpha = evaluate_alpha(self.expr_str, self.data)
        self.alpha_series = alpha
        self._positions = compute_positions(
            self.template, alpha, self.direction, self.position_scale,
            self.window, self.z_score_threshold, self.threshold_upper, self.threshold_lower,
        )


class BooleanMCTSStrategy(_TemplateStrategy):
    template = "BOOLEAN"


class RatioMCTSStrategy(_TemplateStrategy):
    template = "RATIO"


class NormalizedMCTSStrategy(_TemplateStrategy):
    template = "NORMALIZED"


class SearchSession:
    """State of one blueprint's search between `continue_search` calls: the tree and the stopping counters."""

    def __init__(self, root_node: 'MCTSNode'):
        self.root_node = root_node
        self.iterations = 0
        self.best_reward = -float('inf')
        self.no_improvement = 0
        self.stop_reason: Optional[str] = None


class _FixedPositions:
    """Adapter so precomputed positions can go through AlphaBacktestEngine.run."""
    def __init__(self, positions: pd.Series):
        self.positions = positions

    def run_algorithm(self, df):
        return self.positions

class MCTSEngine:
    """
    Monte Carlo Tree Search Engine for alpha expression discovery.
    
    Note on Depth:
        `MCTSEngine` defaults to a `max_depth` of 4. When creating an `MCTSState`, 
        the engine overrides the state's default `max_depth` of 3 with its own 
        configured depth (typically 4).
    """
    def __init__(self, timeframe: str = '10m', max_depth: int = MCTS_MAX_DEPTH, exploration_c: float = 1.414, global_position_matrix: pd.DataFrame = None, seed: Optional[int] = None, data: Optional[pd.DataFrame] = None, reward_mode: Optional[str] = None):
        """
        Initialize the MCTSEngine.
        
        Parameters
        ----------
        timeframe : str, default '10m'
            The data timeframe; selects window scaling and, when `data` is None, the file to load.
        max_depth : int, default 4
            The maximum formula tree depth. Overrides MCTSState's default of 3.
        exploration_c : float, default 1.414
            Exploration constant for UCT child selection.
        global_position_matrix : Optional[pd.DataFrame], default None
            Matrix of historical position series used for correlation penalty.
        seed : Optional[int], default None
            Seed of the engine's private random generator. All search randomness (expansion,
            rollout, tie-breaks) goes through it; the same seed on the same data and blueprint
            reproduces the same search. None seeds from the OS.
        data : Optional[pd.DataFrame], default None
            OHLCV frame to search on (datetime index). The engine reads nothing beyond it, so a
            sub-window or synthetic frame can be injected. None loads `load_data(timeframe)`.
        reward_mode : Optional[str], default None
            One of AppConfig.REWARD_MODES (see `evaluate_expression`); None takes AppConfig.REWARD_MODE.
        """
        if reward_mode is None:
            reward_mode = REWARD_MODE
        if reward_mode not in REWARD_MODES:
            raise ValueError(f"reward_mode must be one of {REWARD_MODES}, got {reward_mode!r}")
        self.reward_mode = reward_mode
        self.seed = seed
        self.rng = random.Random(seed)
        self.timeframe = timeframe
        self.max_depth = max_depth
        self.exploration_c = exploration_c
        self.global_position_matrix = global_position_matrix
        
        scale = BASELINE_TF_MINUTES / TIMEFRAME_MINUTES.get(timeframe, 10)
        self.scaled_periods, self.scaled_window_search = scaled_ladders(timeframe)
        
        print(f"[MCTS] Timeframe: {timeframe} | Scale: {scale:.1f}x")
        print(f"[MCTS] Scaled PERIODS: {self.scaled_periods}")
        print(f"[MCTS] Scaled Window Search: {self.scaled_window_search}")
        print(f"[MCTS] Seed: {seed}")
        
        if data is None:
            print(f"[MCTS] Loading data for {timeframe}...")
            data = load_data(timeframe)
        # Copy so filling Volume never mutates the caller's frame.
        self.df = data.copy()
        self.df['Volume'] = self.df['Volume'].fillna(0.0)
        # Use full historical data for MCTS due to vectorized engine speedup
        self.df_search = self.df
            
        self.backtest_engine = AlphaBacktestEngine()
        self.cache: Dict[str, tuple] = {}
        self.max_cache_size = 50000
        self.leaderboard: List[Dict[str, Any]] = []
        
        self.data = AlphaDataProxy(self.df_search)

        # Evaluation failures: distinct "Type: message" -> count. An evaluation that raises scores
        # -10, so a run where everything fails would otherwise look like a run with no good alpha.
        self.error_counts: Counter = Counter()
        self.evaluation_count = 0
        self.failed_evaluation_count = 0
        # Evaluations that ran without error but where no direction passed the hard gate (reward -10).
        self.gated_evaluation_count = 0
        self.gate_reasons: Counter = Counter()

    def compute_rank_ic(self, alpha_series: pd.Series, close_series: pd.Series) -> float:
        fwd_returns = close_series.pct_change(1).shift(-1)
        if (alpha_series.index.equals(fwd_returns.index) and alpha_series.dtype == np.float64
                and fwd_returns.dtype == np.float64):
            # Same index and dtype: the arrays below are exactly what the pandas path hands to scipy,
            # so the result is identical without the DataFrame / Series.corr overhead.
            a = alpha_series.to_numpy()
            b = fwd_returns.to_numpy()
            keep = ~(np.isnan(a) | np.isnan(b))
            if not keep.all():
                a = a[keep]
                b = b[keep]
            if len(a) < 20:
                return 0.0
            if _sample_std(a) == 0.0 or _sample_std(b) == 0.0:
                return 0.0
            return spearmanr(a, b)[0]
        valid = pd.DataFrame({'alpha': alpha_series, 'fwd_ret': fwd_returns}).dropna()
        if len(valid) < 20:
            return 0.0
        # Prevent pandas ConstantInput warning when input series is constant (standard deviation is 0)
        if valid['alpha'].std() == 0.0 or valid['fwd_ret'].std() == 0.0:
            return 0.0
        return valid['alpha'].corr(valid['fwd_ret'], method='spearman')

    def _ic_input(self, desc: Dict[str, Any], alpha_val: pd.Series) -> pd.Series:
        """
        Series whose rank IC enters the reward. "sharpe" mode scores the traded signal, so a NORMALIZED
        candidate uses the rolling z-score of the alpha (the one `compute_positions` thresholds); every
        other case uses the raw alpha. Rolling warm-up stays in `alpha_val`, so slice after calling.
        """
        if self.reward_mode == "sharpe" and desc['template'] == "NORMALIZED":
            return ts_zscore(alpha_val, desc['window'])
        return alpha_val

    def _record_error(self, stage: str, exc: Exception) -> None:
        key = f"{type(exc).__name__}: {exc}"[:200]
        self.error_counts[key] += 1
        if self.error_counts[key] == 1:
            logger.warning("[MCTS] evaluation error during %s: %s", stage, key)

    def error_summary(self) -> Dict[str, Any]:
        """Counts of evaluations and of those that raised, plus the most frequent messages."""
        return {
            'evaluations': self.evaluation_count,
            'failed_evaluations': self.failed_evaluation_count,
            'gated_evaluations': self.gated_evaluation_count,
            'gate_reasons': dict(self.gate_reasons),
            'top_errors': self.error_counts.most_common(5),
        }

    def _reward_over_directions(self, alpha_val: pd.Series, rank_ic: float, df: pd.DataFrame,
                                desc: Dict[str, Any], info: Dict[str, Any], bars: Optional[pd.Index] = None,
                                directions: tuple = (1.0, -1.0)) -> tuple:
        """
        Best reward over both directions for one alpha (the reward formula of `evaluate_expression`).

        `alpha_val` is aligned with `df`. Positions are computed on the whole of `alpha_val` (so rolling
        windows keep their warm-up); when `bars` is given only those bars are traded and scored.
        `directions` lists the trade directions tried; the best one counts. Returns (reward, direction, metrics, failed, passed_gate, gate_too_few_trades).
        """
        best_reward = -10.0
        best_direction = 1.0
        best_metrics = dict(info)
        failed = False
        passed_gate = False
        gate_too_few_trades = []  # per direction: True when the hard gate failed on trade count
        pos_scale = NormalizedMCTSStrategy.position_scale
        template_type, window, z_score_thresh = desc['template'], desc['window'], desc['z_score_threshold']
        scored_df = df if bars is None else df.loc[bars]
        for direction in directions:
            try:
                pos_series = compute_positions(
                    template_type, alpha_val, direction, pos_scale, window, z_score_thresh,
                    desc['threshold_upper'], desc['threshold_lower'],
                )
                if bars is not None:
                    pos_series = pos_series.loc[bars]
                result = self.backtest_engine.run(_FixedPositions(pos_series), scored_df)
                metrics = compute_metrics(result)

                calmar = metrics.get('calmar_ratio', 0.0)
                if calmar is None or np.isnan(calmar):
                    calmar = 0.0

                total_trades = metrics.get('total_trades', 0)
                calmar_threshold = MCTS_QUALITY_THRESHOLDS['calmar_ratio']
                too_few_trades = total_trades < MIN_TRADES
                sharpe = metrics.get('sharpe_ratio', 0.0)
                if sharpe is None or np.isnan(sharpe):
                    sharpe = 0.0
                if self.reward_mode == "gated" and (too_few_trades or calmar < calmar_threshold):
                    reward = -10.0
                    gate_too_few_trades.append(too_few_trades)
                else:
                    passed_gate = True
                    max_corr = 0.0
                    if self.global_position_matrix is not None and not self.global_position_matrix.empty:
                        common_idx = pos_series.index.intersection(self.global_position_matrix.index)
                        if len(common_idx) > 20:
                            # Align and forward fill inside corrwith if needed, but indices should match
                            corrs = self.global_position_matrix.loc[common_idx].corrwith(pos_series.loc[common_idx])
                            max_corr = corrs.abs().max()
                            if np.isnan(max_corr):
                                max_corr = 0.0

                    if too_few_trades:
                        s_calmar = 0.0  # only reachable in "soft" / "sharpe" mode
                    elif self.reward_mode == "sharpe":
                        # Annualised Sharpe in the Calmar slot: no gate, zero point at Sharpe 0.
                        s_calmar = min(1.0, max(0.0, sharpe / REWARD_WEIGHTS['max_sharpe']))
                    else:
                        s_calmar = min(1.0, max(0.0, (calmar - calmar_threshold) / (REWARD_WEIGHTS['max_calmar'] - calmar_threshold)))
                    s_ic = min(1.0, abs(rank_ic) / REWARD_WEIGHTS['max_ic'])
                    s_corr = max(0.0, 1.0 - max_corr)

                    reward = (REWARD_WEIGHTS['calmar_weight'] * s_calmar + REWARD_WEIGHTS['ic_weight'] * s_ic) * s_corr

                if reward > best_reward:
                    best_reward = reward
                    best_direction = direction
                    best_metrics = dict(metrics)
                    best_metrics.update(info)
                    best_metrics['rank_ic'] = rank_ic
            except Exception as exc:
                failed = True
                self._record_error("backtest", exc)
        return best_reward, best_direction, best_metrics, failed, passed_gate, gate_too_few_trades

    def score_on_span(self, candidate: Dict[str, Any], frame: pd.DataFrame, start: str, end: str) -> float:
        """
        Reward of a leaderboard candidate on the bars of `frame` from `start` to `end` (inclusive),
        by the same formula as `evaluate_expression` (this engine's reward mode and correlation matrix).

        The alpha and the positions are computed on the whole of `frame`, so rolling windows have
        their warm-up before `start`; only the bars in the span are traded and scored (rank IC
        included). Bars after `end` never enter the span, but pass a frame that stops there anyway.
        Only the candidate's own direction is traded (the one fixed on the search data), so the
        score judges that strategy, not the better of two. Returns -10.0 when the expression fails.
        """
        desc = {
            'expr': candidate['expr'], 'template': candidate['template'], 'window': candidate['window'],
            'z_score_threshold': candidate['z_score'], 'threshold_upper': candidate['threshold_upper'],
            'threshold_lower': candidate['threshold_lower'],
        }
        frame = frame.copy()
        frame['Volume'] = frame['Volume'].fillna(0.0)
        bars = frame.loc[start:end].index
        try:
            alpha_val = evaluate_alpha(desc['expr'], AlphaDataProxy(frame))
            ic_alpha = self._ic_input(desc, alpha_val)
            rank_ic = self.compute_rank_ic(ic_alpha.loc[bars].astype(np.float64), frame.loc[bars, 'Close'])
        except Exception as exc:
            self._record_error("expression", exc)
            return -10.0
        return self._reward_over_directions(alpha_val, rank_ic, frame, desc, dict(desc), bars,
                                            directions=(candidate['direction'],))[0]

    def evaluate_expression(self, ast_tree: ASTNode) -> tuple:
        """
        Evaluate the trading performance of an AST tree by running a backtest.

        Uses an evaluation cache (`self.cache`) to store previous backtest results
        based on the generated expression string, window, and z-score threshold.

        An exception while rendering, evaluating or backtesting scores -10 but is counted in
        `self.error_counts` and logged on first occurrence.

        Reward = (0.6 * S_calmar + 0.4 * S_ic) * S_corr, S_corr from the position correlation
        against global_position_matrix. `self.reward_mode` decides what happens to weak candidates:
        - "gated": total_trades < MIN_TRADES or Calmar below the threshold -> reward -10.0.
        - "soft": no gate; S_calmar is 0 when total_trades < MIN_TRADES, the IC term stays.
        - "sharpe": no gate; S_calmar is replaced by clip(Sharpe / max_sharpe, 0, 1) (0 when
          total_trades < MIN_TRADES), and for NORMALIZED the IC is taken on the rolling z-score.

        Parameters
        ----------
        ast_tree : ASTNode
            The AST tree representing the strategy or formula.

        Returns
        -------
        tuple
            A tuple of (best_reward, best_direction, best_metrics). best_metrics always carries
            'template', 'window', 'z_score_threshold', 'threshold_upper', 'threshold_lower'.
        """
        try:
            desc = describe_candidate(ast_tree)
        except Exception as exc:
            self.evaluation_count += 1
            self.failed_evaluation_count += 1
            self._record_error("render", exc)
            return -10.0, 1.0, {}

        template_type = desc['template']
        window = desc['window']
        z_score_thresh = desc['z_score_threshold']
        cache_key = desc['cache_key']
        if cache_key in self.cache:
            return self.cache[cache_key]

        self.evaluation_count += 1
        info = {
            'template': template_type,
            'window': window,
            'z_score_threshold': z_score_thresh,
            'threshold_upper': desc['threshold_upper'],
            'threshold_lower': desc['threshold_lower'],
        }
        try:
            alpha_val = evaluate_alpha(desc['expr'], self.data)
            rank_ic = self.compute_rank_ic(self._ic_input(desc, alpha_val).astype(np.float64), self.df_search['Close'])
        except Exception as exc:
            self._record_error("expression", exc)
            self.failed_evaluation_count += 1
            best_metrics = dict(info)
            self.cache[cache_key] = (-10.0, 1.0, best_metrics)
            return -10.0, 1.0, best_metrics

        best_reward, best_direction, best_metrics, failed, passed_gate, gate_too_few_trades = \
            self._reward_over_directions(alpha_val, rank_ic, self.df_search, desc, info)

        if failed:
            self.failed_evaluation_count += 1
        elif not passed_gate:
            self.gated_evaluation_count += 1
            self.gate_reasons["too_few_trades" if all(gate_too_few_trades) else "low_calmar"] += 1

        if len(self.cache) > self.max_cache_size:
            # Evict the oldest 50% of cache entries (FIFO based on insertion order)
            keys = list(self.cache.keys())
            for k in keys[:len(keys) // 2]:
                self.cache.pop(k, None)
            import gc
            gc.collect()

        self.cache[cache_key] = (best_reward, best_direction, best_metrics)
        return best_reward, best_direction, best_metrics

    def start_search(self, root_ast: ASTNode) -> 'SearchSession':
        """
        Check a blueprint and open a resumable search on it; no iteration runs yet. `continue_search`
        advances it, in as many calls as wanted, keeping the tree, the visit counts and the stopping counters.
        """
        unimplemented = find_unimplemented_operator(root_ast)
        if unimplemented is not None:
            raise ValueError(f"Blueprint uses operator '{unimplemented}', which has no code generation")
        analysis = analyze_dimensions(root_ast, self.max_depth)
        if analysis.error:
            raise ValueError(f"Blueprint cannot be completed at max_depth={self.max_depth}: {analysis.error}")
        root_state = MCTSState(root_ast, self.max_depth, self.scaled_window_search, self.scaled_periods)
        return SearchSession(MCTSNode(root_state))

    def run_search_from_blueprint(
        self,
        root_ast: ASTNode,
        n_iterations: int = 100,
        on_progress: Optional[Callable[[dict], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        progress_interval_s: float = 2.0,
    ) -> str:
        """
        Run MCTS to expand an AST tree blueprint into trading strategies (`start_search` then one
        `continue_search` of `n_iterations`).

        Every `progress_interval_s` seconds (every iteration when 0) `on_progress(snapshot)` is
        called, then `should_stop()`; a True result ends the search. The callbacks never touch
        `self.rng`, so the search order is the same with or without them. After the loop
        `on_progress` is called once more with the final snapshot plus `stop_reason`.

        Returns the stop reason: "budget", "patience", "entropy" or "stopped".
        """
        session = self.start_search(root_ast)
        return self.continue_search(session, n_iterations, on_progress, should_stop, progress_interval_s)

    def continue_search(
        self,
        session: 'SearchSession',
        n_iterations: int,
        on_progress: Optional[Callable[[dict], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
        progress_interval_s: float = 2.0,
        early_stop: bool = True,
    ) -> str:
        """
        Advance `session` by up to `n_iterations` iterations (same callbacks and return value as
        `run_search_from_blueprint`). The entropy check, the patience counter and the periodic log
        count the session's iterations since `start_search`, not those of this call, so splitting a
        search into chunks gives the same tree and leaderboard as one long call. `early_stop=False`
        turns the entropy and patience stops off, so the whole budget is spent. A session that already
        stopped on entropy or patience returns that reason without running.
        """
        if session.stop_reason in ("entropy", "patience"):
            return session.stop_reason
        root_node = session.root_node
        print(f"[MCTS] Search from Blueprint | Depth: {self.max_depth} | Iterations: {n_iterations}")

        start_time = time.time()
        stop_reason = "budget"
        completed = 0
        last_report = time.monotonic()

        def snapshot() -> dict:
            return {
                'iteration': completed,
                'n_iterations': n_iterations,
                'best_reward': max(x['reward'] for x in self.leaderboard) if self.leaderboard else None,
                'evaluations': self.evaluation_count,
                'failed_evaluations': self.failed_evaluation_count,
                'gated_evaluations': self.gated_evaluation_count,
                'elapsed_s': time.time() - start_time,
            }

        for _ in range(n_iterations):
            i = session.iterations + 1
            if i % 500 == 0:
                import gc
                gc.collect()

            if i % 10 == 0:
                elapsed = time.time() - start_time
                print(f"  [MCTS] Iteration {i} | Cache size: {len(self.cache)} | Best reward: {max([x['reward'] for x in self.leaderboard]) if self.leaderboard else 'N/A'} | Elapsed: {elapsed:.1f}s")

            # Entropy Convergence Check
            if early_stop and i >= REWARD_WEIGHTS['burn_in'] and i % 500 == 0:
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
                        stop_reason = "entropy"
                        break

            node = root_node
            path = [node]
            while node.is_fully_expanded() and not node.is_leaf():
                node = self.select_best_child(node)
                path.append(node)

            if not node.state.is_terminal():
                if not node.is_fully_expanded():
                    action = node.untried_actions.pop(self.rng.randrange(len(node.untried_actions)))
                    new_state = node.state.apply_action(action)
                    child_node = MCTSNode(new_state, parent=node, action_leading_here=action)
                    node.children.append(child_node)
                    node = child_node
                    path.append(node)

            terminal_state = self.rollout(node.state)
            reward, direction, metrics = self.evaluate_expression(terminal_state.ast_tree)

            if terminal_state.is_terminal():
                try:
                    desc = describe_candidate(terminal_state.ast_tree)
                except ValueError:
                    desc = None  # already counted as a render error by evaluate_expression
                if desc is not None:
                    self.update_leaderboard(desc['expr'], reward, direction, metrics)

            # Risk-Seeking Backpropagation (Tail Quantile)
            for p_node in path:
                p_node.visit_count += 1
                if reward > p_node.max_reward:
                    p_node.max_reward = reward
            session.iterations += 1
            completed += 1

            # Early Stopping (Patience Check)
            if self.leaderboard:
                max_reward = max(x['reward'] for x in self.leaderboard)
                if max_reward > session.best_reward:
                    session.best_reward = max_reward
                    session.no_improvement = 0
                else:
                    session.no_improvement += 1

                if early_stop and session.no_improvement >= REWARD_WEIGHTS.get('patience', 5000):
                    print(f"\n[MCTS] Early Stopping triggered after {session.no_improvement} iterations without improvement!")
                    stop_reason = "patience"
                    break

            if on_progress is not None or should_stop is not None:
                now = time.monotonic()
                if now - last_report >= progress_interval_s:
                    last_report = now
                    if on_progress is not None:
                        on_progress(snapshot())
                    if should_stop is not None and should_stop():
                        stop_reason = "stopped"
                        break

        session.stop_reason = stop_reason if stop_reason in ("entropy", "patience") else None
        print(f"[MCTS] Search completed in {time.time() - start_time:.1f}s.")
        summary = self.error_summary()
        print(f"[MCTS] Evaluations: {summary['evaluations']} | Failed with an exception: {summary['failed_evaluations']} | Gated (-10): {summary['gated_evaluations']} {summary['gate_reasons']}")
        for message, count in summary['top_errors']:
            print(f"[MCTS]   {count} x {message}")
        if summary['evaluations'] > 0 and summary['failed_evaluations'] == summary['evaluations']:
            logger.error("[MCTS] Every evaluation raised an exception; the search found nothing.")
        if on_progress is not None:
            final = snapshot()
            final['stop_reason'] = stop_reason
            on_progress(final)
        return stop_reason

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
                
        return best_child or self.rng.choice(node.children)

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
            action = self.rng.choice(actions)
            curr_state = curr_state.apply_action(action)
        return curr_state

    def update_leaderboard(self, expr_str: str, reward: float, direction: float, metrics: dict):
        """
        Update the rolling leaderboard cache with a newly evaluated candidate.
        """
        template = metrics.get('template', 'BOOLEAN')
        window = metrics.get('window', 20)
        z_score = metrics.get('z_score_threshold', 1.0)
        threshold_upper = metrics.get('threshold_upper', 70.0)
        threshold_lower = metrics.get('threshold_lower', 30.0)
        
        for item in self.leaderboard:
            if item['expr'] == expr_str and item.get('template') == template and item.get('window') == window and item.get('z_score') == z_score and item.get('threshold_upper') == threshold_upper and item.get('threshold_lower') == threshold_lower:
                return
        
        self.leaderboard.append({
            'expr': expr_str,
            'template': template,
            'reward': reward,
            'direction': direction,
            'window': window,
            'z_score': z_score,
            'threshold_upper': threshold_upper,
            'threshold_lower': threshold_lower,
            'metrics': metrics
        })
        self.leaderboard.sort(key=lambda x: x['reward'], reverse=True)
        self.leaderboard = self.leaderboard[:100] # Rolling Window Cache bounds

    def get_best_candidates(self) -> List[Dict[str, Any]]:
        return self.leaderboard
