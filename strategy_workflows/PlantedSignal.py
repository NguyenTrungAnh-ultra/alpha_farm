"""
PlantedSignal
=============
Builds placebo price series with a known formula planted in them, and the checks used to
decide whether a search recovered that formula.

Placebo base: the bar-to-bar returns of a real series are permuted inside each segment, every
bar keeping its own Volume and intrabar shape (Open/High/Low as ratios of its own Close), then
prices are rebuilt from the returns. Planting adds a predictable part to each return:

    s_t     = signal computed from the rebuilt closes up to bar t only
    r_{t+1} = eps_{t+1} + beta * sigma * s_t

realized (Spearman) IC is measured. One beta >= 0 per strength is calibrated so that the mean
realized IC on the search segment over a fixed set of calibration permutations equals the
target; all run seeds and both segments share it, so a run's IC is target plus sample noise.
"""

import ast
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core_engine.AlphaPrimitives import ts_mean, ts_zscore
from strategy_workflows.MCTSDimensions import OPERATOR_REGISTRY, OperatorGroup
from strategy_workflows.MCTSEngine import ast_to_code
from strategy_workflows.SemanticCompiler import ASTNode

SEARCH_START = '2018-08-13'
SEARCH_END = '2020-06-30'
EVAL_START = '2020-07-01'
EVAL_END = '2020-12-31'

# Positions are scaled like the leaderboard evaluation (NormalizedMCTSStrategy.position_scale).
TOP_K = 5
EXACT_STEP_TOLERANCE = 1
NEAR_CORRELATION = 0.7


# --------------------------------------------------------------------------- formula


@dataclass(frozen=True)
class PlantedFormula:
    """
    The planted alpha A = close - ts_mean(close, period) and signal s = ts_zscore(A, window).

    `period` must be one of the engine's scaled periods and `window` one of its scaled z-score
    windows for the timeframe, otherwise the search can never produce the formula.
    """
    period: int = 10
    window: int = 10

    @property
    def lookback(self) -> int:
        # Closes needed to compute s at one bar: `period` for the mean, then `window` values of A.
        return self.period + self.window - 1

    def expr_ast(self) -> ASTNode:
        return ASTNode(name='sub', children=[
            ASTNode(name='pv_close'),
            ASTNode(name='ts_mean', children=[ASTNode(name='pv_close')], window=self.period),
        ])

    @property
    def expr(self) -> str:
        """Expression text exactly as the search renders it."""
        return ast_to_code(self.expr_ast())

    def signal_last(self, closes: np.ndarray) -> float:
        """Signal at the last bar of `closes` (NaN when fewer than `lookback` closes)."""
        if len(closes) < self.lookback:
            return float('nan')
        closes = np.asarray(closes[-self.lookback:], dtype=np.float64)
        alpha = closes - ts_mean(closes, self.period)
        return float(ts_zscore(alpha, self.window)[-1])

    def alpha_series(self, close: pd.Series) -> pd.Series:
        return close - ts_mean(close, self.period)

    def signal_series(self, close: pd.Series) -> pd.Series:
        return ts_zscore(self.alpha_series(close), self.window)


PLANTED_FORMULA = PlantedFormula()


def assert_in_search_space(engine, formula: PlantedFormula = PLANTED_FORMULA) -> None:
    """Fail loudly when the engine's scaled windows cannot express the planted formula."""
    if formula.period not in engine.scaled_periods:
        raise ValueError(f"Planted period {formula.period} not in scaled_periods {engine.scaled_periods}")
    if formula.window not in engine.scaled_window_search:
        raise ValueError(f"Planted window {formula.window} not in scaled_window_search {engine.scaled_window_search}")


# --------------------------------------------------------------------------- placebo base


def split_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Per-bar record: close-to-close return (0 for the first bar), Volume and intrabar shape."""
    close = df['Close'].to_numpy(dtype=np.float64)
    ret = np.zeros(len(df))
    ret[1:] = close[1:] / close[:-1] - 1.0
    return pd.DataFrame({
        'ret': ret,
        'Volume': df['Volume'].to_numpy(dtype=np.float64),
        'open_ratio': (df['Open'] / df['Close']).to_numpy(dtype=np.float64),
        'high_ratio': (df['High'] / df['Close']).to_numpy(dtype=np.float64),
        'low_ratio': (df['Low'] / df['Close']).to_numpy(dtype=np.float64),
    }, index=df.index)


def permute_returns(bars: pd.DataFrame, rng: np.random.Generator, keep_first: bool = False) -> pd.DataFrame:
    """
    Shuffle whole bar records (return, Volume, shape together) inside one segment.

    The index stays in place. `keep_first` pins the first row, used for the very first bar of the
    series whose return is a placeholder 0.
    """
    n = len(bars)
    start = 1 if keep_first else 0
    order = np.arange(n)
    order[start:] = start + rng.permutation(n - start)
    out = bars.iloc[order].copy()
    out.index = bars.index
    return out


def build_ohlcv_from_returns(bars: pd.DataFrame, returns: np.ndarray, first_close: float) -> pd.DataFrame:
    """Rebuild OHLCV: Close from the cumulative product of (1 + return), shape ratios from `bars`."""
    returns = np.asarray(returns, dtype=np.float64).copy()
    returns[0] = 0.0
    close = first_close * np.cumprod(1.0 + returns)
    return pd.DataFrame({
        'Open': close * bars['open_ratio'].to_numpy(),
        'High': close * bars['high_ratio'].to_numpy(),
        'Low': close * bars['low_ratio'].to_numpy(),
        'Close': close,
        'Volume': bars['Volume'].to_numpy(),
    }, index=bars.index)


@dataclass
class PlantResult:
    returns: np.ndarray   # planted returns, index 0 is 0
    closes: np.ndarray    # first_close * cumprod(1 + returns)
    signal: np.ndarray    # s_t before NaN -> 0; NaN during warm-up


def plant_signal(
    eps: np.ndarray,
    sigma: np.ndarray,
    first_close: float,
    beta: float,
    signal_fn: Callable[[np.ndarray], float],
    lookback: int,
) -> PlantResult:
    """
    Sequentially add the predictable part to placebo returns `eps`.

    For each bar t the signal is computed from the reconstructed closes up to t (a trailing
    window of `lookback` closes is enough for the formula), then the next return becomes
    eps[t+1] + beta * sigma[t+1] * s_t, with NaN signals counted as 0. Index 0 carries no return.
    `sigma[i]` is the placebo return std of the segment that bar i belongs to.
    """
    n = len(eps)
    returns = np.zeros(n)
    cumulative = np.ones(n)
    closes = np.empty(n)
    closes[0] = first_close
    signal = np.full(n, np.nan)
    for t in range(n):
        window = closes[max(0, t - lookback + 1): t + 1]
        s_t = signal_fn(window)
        signal[t] = s_t
        if t + 1 < n:
            drive = 0.0 if np.isnan(s_t) else s_t
            returns[t + 1] = eps[t + 1] + beta * sigma[t + 1] * drive
            cumulative[t + 1] = cumulative[t] * (1.0 + returns[t + 1])
            closes[t + 1] = first_close * cumulative[t + 1]
    return PlantResult(returns=returns, closes=closes, signal=signal)


def realized_ic(signal: pd.Series, close: pd.Series) -> float:
    """Spearman IC of `signal` against the next-bar return (same definition as MCTSEngine.compute_rank_ic)."""
    fwd_returns = close.pct_change(1).shift(-1)
    valid = pd.DataFrame({'alpha': signal, 'fwd_ret': fwd_returns}).dropna()
    if len(valid) < 20:
        return 0.0
    if valid['alpha'].std() == 0.0 or valid['fwd_ret'].std() == 0.0:
        return 0.0
    return float(valid['alpha'].corr(valid['fwd_ret'], method='spearman'))


CALIBRATION_TOLERANCE = 0.002
CALIBRATION_MAX_ITERATIONS = 30
CALIBRATION_INITIAL_STEP = 0.05
CALIBRATION_SEEDS = tuple(range(1001, 1021))


def placebo_arrays(bars: pd.DataFrame, n_search: int, seed: int):
    """
    Permuted bar records, placebo returns and per-bar sigma for one seed.

    Each segment is permuted separately by one seeded generator; sigma is the plain std of the
    segment's permuted returns, repeated for every bar of the segment.
    """
    rng = np.random.default_rng(seed)
    perm_search = permute_returns(bars.iloc[:n_search], rng, keep_first=True)
    perm_eval = permute_returns(bars.iloc[n_search:], rng)
    perm = pd.concat([perm_search, perm_eval])
    eps = perm['ret'].to_numpy()
    sigma = np.empty(len(eps))
    sigma[:n_search] = perm_search['ret'].iloc[1:].std()
    sigma[n_search:] = perm_eval['ret'].std() if len(perm_eval) > 1 else 0.0
    return perm, eps, sigma


def search_ic_for_seed(
    bars: pd.DataFrame, n_search: int, first_close: float, beta: float, seed: int,
    formula: PlantedFormula = PLANTED_FORMULA,
) -> float:
    """Realized search-segment IC of the signal planted with `beta` on the placebo of `seed`."""
    _, eps, sigma = placebo_arrays(bars, n_search, seed)
    planted = plant_signal(eps[:n_search], sigma[:n_search], first_close, beta,
                           formula.signal_last, formula.lookback)
    return realized_ic(pd.Series(planted.signal), pd.Series(planted.closes))


def _ic_job(job: tuple) -> float:
    return search_ic_for_seed(*job)


@dataclass
class Calibration:
    beta: float
    mean_ic: float
    std_ic: float
    seeds: List[int]
    iterations: int


def calibrate_beta(
    base: pd.DataFrame,
    search_end: str,
    target_ic: float,
    formula: PlantedFormula = PLANTED_FORMULA,
    seeds: Sequence[int] = CALIBRATION_SEEDS,
    tolerance: float = CALIBRATION_TOLERANCE,
    max_iterations: int = CALIBRATION_MAX_ITERATIONS,
    workers: int = 1,
) -> Calibration:
    """
    One beta >= 0 whose MEAN realized search-segment IC over the calibration permutations
    equals `target_ic` (within `tolerance` on the mean).

    The calibration seeds are distinct from run seeds, so the placebo's own chance IC averages
    out instead of being cancelled per seed. A zero target gives beta 0 exactly. Doubling to
    bracket the target, then bisection; no randomness.
    """
    seeds = list(seeds)
    if target_ic == 0.0:
        return Calibration(0.0, float('nan'), float('nan'), seeds, 0)
    bars = split_bars(base)
    n_search = len(base.loc[:search_end])
    first_close = float(base['Close'].iloc[0])
    pool = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None

    def ics(beta: float) -> List[float]:
        jobs = [(bars, n_search, first_close, beta, seed, formula) for seed in seeds]
        return list(pool.map(_ic_job, jobs)) if pool else [_ic_job(j) for j in jobs]

    def gap(beta: float):
        values = ics(beta)
        return float(np.mean(values)) - target_ic, values

    try:
        g0, v0 = gap(0.0)
        if g0 >= -tolerance:
            return Calibration(0.0, float(np.mean(v0)), float(np.std(v0, ddof=1)), seeds, 1)
        inner, outer = 0.0, CALIBRATION_INITIAL_STEP
        g_outer, v_outer = gap(outer)
        evaluations = 2
        while g_outer < 0:
            inner, outer = outer, outer * 2.0
            if outer > 1e3:
                raise ValueError("Could not bracket the target IC")
            g_outer, v_outer = gap(outer)
            evaluations += 1
        best = (abs(g_outer), outer, v_outer)
        for _ in range(max_iterations):
            mid = 0.5 * (inner + outer)
            g_mid, v_mid = gap(mid)
            evaluations += 1
            if abs(g_mid) < best[0]:
                best = (abs(g_mid), mid, v_mid)
            if abs(g_mid) <= tolerance:
                break
            if g_mid < 0:
                inner = mid
            else:
                outer = mid
        _, beta, values = best
        return Calibration(beta, float(np.mean(values)), float(np.std(values, ddof=1)), seeds, evaluations)
    finally:
        if pool:
            pool.shutdown()


@dataclass
class PlantedData:
    full: pd.DataFrame          # continuous planted OHLCV over search + evaluation
    search: pd.DataFrame
    evaluation: pd.DataFrame
    signal: pd.Series           # s_t over `full`, NaN during warm-up
    strength: float
    seed: int
    beta: float
    ic_search: float
    ic_eval: float


def build_planted_data(
    base: pd.DataFrame,
    search_end: str,
    strength: float,
    seed: int,
    beta: float,
    formula: PlantedFormula = PLANTED_FORMULA,
) -> PlantedData:
    """
    Placebo-plus-signal series from a real OHLCV frame covering both segments.

    `beta` comes from `calibrate_beta` for `strength` and is shared by all seeds and both
    segments. The evaluation segment continues from the search segment's last rebuilt close,
    and the signal keeps its history across the boundary, so the result is one continuous series.
    """
    n_search = len(base.loc[:search_end])
    if n_search < 2 or n_search >= len(base):
        raise ValueError("Both segments must be non-empty")
    perm, eps, sigma = placebo_arrays(split_bars(base), n_search, seed)
    first_close = float(base['Close'].iloc[0])
    planted = plant_signal(eps, sigma, first_close, beta, formula.signal_last, formula.lookback)
    full = build_ohlcv_from_returns(perm, planted.returns, first_close)
    signal = pd.Series(planted.signal, index=full.index, name='signal')

    search, evaluation = full.iloc[:n_search], full.iloc[n_search:]
    return PlantedData(
        full=full, search=search, evaluation=evaluation, signal=signal,
        strength=strength, seed=seed, beta=beta,
        ic_search=realized_ic(signal.iloc[:n_search], search['Close']),
        ic_eval=realized_ic(signal.iloc[n_search:], evaluation['Close']),
    )


# --------------------------------------------------------------------------- blueprint coverage


def _data_children(node: ASTNode) -> List[ASTNode]:
    """Data arguments of a node; for TIME_SERIES operators the window constant is not one."""
    meta = OPERATOR_REGISTRY.get(node.name)
    if meta is not None and meta["group"] == OperatorGroup.TIME_SERIES:
        arity = len(meta["input_dims"])
        series = [c for c in node.children if c.name != "Constant"]
        return series if len(series) == arity else node.children[:arity]
    return node.children


def _depth_fits(target: ASTNode, depth: int, max_depth: int) -> bool:
    """True when `target` can be built by the search starting from a '?' slot at `depth`."""
    kids = _data_children(target)
    if not kids:
        return depth <= max_depth          # a terminal may sit at the depth limit
    if depth > max_depth - 1:              # an operator needs room for its operands
        return False
    return all(_depth_fits(k, depth + 1, max_depth) for k in kids)


def _unify(blueprint: ASTNode, target: ASTNode, depth: int, max_depth: int) -> bool:
    if blueprint.name == '?':
        return _depth_fits(target, depth, max_depth)
    if blueprint.name != target.name:
        return False
    b_kids, t_kids = _data_children(blueprint), _data_children(target)
    if len(b_kids) != len(t_kids):
        return False
    return all(_unify(b, t, depth + 1, max_depth) for b, t in zip(b_kids, t_kids))


def _has_hole(node: ASTNode) -> bool:
    return node.name == '?' or any(_has_hole(c) for c in _data_children(node))


def _blueprint_body(blueprint: ASTNode) -> Optional[ASTNode]:
    """Expression under a NORMALIZED template root, or None for other roots."""
    if blueprint.name == "normalized_template":
        return blueprint.children[0]
    return None


def can_express(blueprint: ASTNode, expr: ASTNode, max_depth: int = 4) -> bool:
    """
    True when filling the blueprint's '?' slots (a slot matches any subtree that fits the depth
    limit) can give `expr`, under a NORMALIZED template. Window values are ignored: the search
    chooses them.
    """
    body = _blueprint_body(blueprint)
    return body is not None and _unify(body, expr, 1, max_depth)


def is_verbatim(blueprint: ASTNode, expr: ASTNode, max_depth: int = 4) -> bool:
    """True when the blueprint already spells out `expr` with no '?' left (only windows to find)."""
    body = _blueprint_body(blueprint)
    return body is not None and not _has_hole(body) and _unify(body, expr, 1, max_depth)


# --------------------------------------------------------------------------- recovery


def parse_expression(expr: str):
    """
    Parse rendered expression text into (label, children, window) tuples.

    Binary operators map to their registry names; `div`'s `+ 1e-8` guard is dropped; rolling
    calls keep their last integer argument as the window. Raises ValueError on anything else.
    """
    def build(node):
        if isinstance(node, ast.Name):
            return (node.id, (), None)
        if isinstance(node, ast.Constant):
            return ('Constant', (), node.value)
        if isinstance(node, ast.BinOp):
            names = {ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mult', ast.Div: 'div',
                     ast.BitAnd: 'and_', ast.BitOr: 'or_'}
            label = names.get(type(node.op))
            if label is None:
                raise ValueError(f"Unsupported operator in {expr}")
            right = node.right
            if label == 'div' and isinstance(right, ast.BinOp) and isinstance(right.op, ast.Add) \
                    and isinstance(right.right, ast.Constant) and right.right.value == 1e-8:
                right = right.left
            return (label, (build(node.left), build(right)), None)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
            return ('not_', (build(node.operand),), None)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            names = {ast.Gt: 'greater_than', ast.Lt: 'less_than', ast.Eq: 'equal'}
            label = names.get(type(node.ops[0]))
            if label is None:
                raise ValueError(f"Unsupported comparison in {expr}")
            return (label, (build(node.left), build(node.comparators[0])), None)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = node.args
            meta = OPERATOR_REGISTRY.get(node.func.id)
            if meta is not None and meta["group"] == OperatorGroup.TIME_SERIES:
                window_node = args[-1]
                if not (isinstance(window_node, ast.Constant) and isinstance(window_node.value, int)):
                    raise ValueError(f"Missing window in {expr}")
                return (node.func.id, tuple(build(a) for a in args[:-1]), window_node.value)
            return (node.func.id, tuple(build(a) for a in args), None)
        raise ValueError(f"Unsupported syntax in {expr}")

    return build(ast.parse(expr, mode='eval').body)


def _within_steps(value: int, target: int, ladder: Sequence[int], tolerance: int) -> bool:
    if value not in ladder or target not in ladder:
        return False
    return abs(list(ladder).index(value) - list(ladder).index(target)) <= tolerance


def _trees_match(cand, target, periods: Sequence[int], tolerance: int) -> bool:
    c_label, c_kids, c_window = cand
    t_label, t_kids, t_window = target
    if c_label != t_label or len(c_kids) != len(t_kids):
        return False
    if (c_window is None) != (t_window is None):
        return False
    if t_window is not None and not _within_steps(c_window, t_window, periods, tolerance):
        return False
    return all(_trees_match(c, t, periods, tolerance) for c, t in zip(c_kids, t_kids))


def is_exact_recovery(
    candidate: dict,
    formula: PlantedFormula,
    scaled_periods: Sequence[int],
    scaled_window_search: Sequence[int],
    tolerance: int = EXACT_STEP_TOLERANCE,
) -> bool:
    """
    Leaderboard candidate has the planted structure and fields, long direction, NORMALIZED
    template, rolling windows and z-score window each within `tolerance` steps of the planted ones.
    """
    if candidate.get('template') != 'NORMALIZED' or candidate.get('direction') != 1.0:
        return False
    if not _within_steps(candidate.get('window'), formula.window, scaled_window_search, tolerance):
        return False
    try:
        cand_tree = parse_expression(candidate['expr'])
        target_tree = parse_expression(formula.expr)
    except (ValueError, SyntaxError):
        return False
    return _trees_match(cand_tree, target_tree, scaled_periods, tolerance)


def spearman_abs(a: pd.Series, b: pd.Series) -> float:
    """|Spearman| between two aligned series on their jointly valid bars (0 when degenerate)."""
    valid = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(valid) < 20 or valid['a'].std() == 0.0 or valid['b'].std() == 0.0:
        return 0.0
    return abs(float(valid['a'].corr(valid['b'], method='spearman')))


def is_near_recovery(correlation: float, threshold: float = NEAR_CORRELATION) -> bool:
    return correlation >= threshold


# --------------------------------------------------------------------------- top-k portfolio


def top_candidates(leaderboard: List[dict], k: int = TOP_K) -> List[dict]:
    """Best `k` distinct candidates that passed scoring (reward above the -10 failure value)."""
    seen = set()
    picked = []
    for item in sorted(leaderboard, key=lambda x: x['reward'], reverse=True):
        if item['reward'] <= -10.0:
            continue
        key = (item['expr'], item.get('template'), item.get('window'), item.get('z_score'),
               item.get('threshold_upper'), item.get('threshold_lower'), item.get('direction'))
        if key in seen:
            continue
        seen.add(key)
        picked.append(item)
        if len(picked) == k:
            break
    return picked


def combine_positions(positions: List[pd.Series]) -> pd.Series:
    """Equal-weight average: each of the k position series gets weight 1/k."""
    if not positions:
        raise ValueError("No positions to combine")
    k = len(positions)
    combined = positions[0] / k
    for p in positions[1:]:
        combined = combined + p / k
    return combined
