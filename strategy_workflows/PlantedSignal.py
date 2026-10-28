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
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core_engine.AlphaEngine import AlphaDataProxy
from core_engine.AlphaPrimitives import ts_zscore
from strategy_workflows.MCTSDimensions import DATA_FIELD_DIMENSIONS, OPERATOR_REGISTRY, OperatorGroup
from strategy_workflows.MCTSEngine import FIELD_EXPRESSIONS, TS_FUNCTIONS, ast_to_code, evaluate_alpha
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler

SEARCH_START = '2018-08-13'
SEARCH_END = '2020-06-30'
EVAL_START = '2020-07-01'
EVAL_END = '2020-12-31'

# Positions are scaled like the leaderboard evaluation (NormalizedMCTSStrategy.position_scale).
TOP_K = 5
EXACT_STEP_TOLERANCE = 1
NEAR_CORRELATION = 0.7


# --------------------------------------------------------------------------- formula

# Variable names of the generated code that come from the bar shape rather than from Close.
FORMULA_RULE = ("first blueprint in file order with >= 2 '?' slots and a NORMALIZED root; every '?' = pv_close, "
                "every window = 10 (nearest allowed), z-score window 10; a verbatim copy of a blueprint -> next one")
SLOT_FILL_FIELD = 'pv_close'
TARGET_WINDOW = 10


@dataclass(frozen=True)
class PlantedFormula:
    """
    A planted alpha A (`tree`, every ts_* node has a window) and its signal s = ts_zscore(A, z_window).

    The windows must be values the engine's scaled periods / z-score windows offer for the
    timeframe, otherwise the search can never produce the formula (`assert_in_search_space`).
    """
    tree: ASTNode = field(compare=False)
    z_window: int
    source: str = ''
    rule: str = ''

    @property
    def expr(self) -> str:
        """Expression text exactly as the search renders it."""
        return ast_to_code(self.tree)

    def expr_ast(self) -> ASTNode:
        return self.tree

    @property
    def windows(self) -> List[int]:
        return sorted(set(_collect_windows(self.tree)))

    @property
    def used_fields(self) -> List[str]:
        """Variable names (open_/high/low/close/volume) the expression reads."""
        return sorted({FIELD_EXPRESSIONS[n] for n in _collect_fields(self.tree)})

    @property
    def lookback(self) -> int:
        """Bars needed to compute s at one bar: deepest chain of nested windows, then the z-score window."""
        return _history_needed(self.tree) + self.z_window

    def signal_last(self, window: Dict[str, np.ndarray]) -> float:
        """
        Signal at the last bar of a trailing window of bars (keys: the variable names in
        `used_fields` plus close, each a 1-D array of equal length). NaN when fewer than `lookback` bars.
        """
        if len(window['close']) < self.lookback:
            return float('nan')
        namespace = {k: np.asarray(v[-self.lookback:], dtype=np.float64) for k, v in window.items()}
        namespace.update(TS_FUNCTIONS)
        alpha = eval(_compiled_expression(self.expr), {"__builtins__": {}}, namespace)
        return float(ts_zscore(alpha, self.z_window)[-1])

    def alpha_series(self, frame: pd.DataFrame) -> pd.Series:
        return evaluate_alpha(self.expr, AlphaDataProxy(frame))

    def signal_series(self, frame: pd.DataFrame) -> pd.Series:
        return ts_zscore(self.alpha_series(frame), self.z_window)


@lru_cache(maxsize=None)
def _compiled_expression(expr: str):
    return compile(expr, '<planted>', 'eval')


def _data_children(node: ASTNode) -> List[ASTNode]:
    """Data arguments of a node; for TIME_SERIES operators the window constant is not one."""
    meta = OPERATOR_REGISTRY.get(node.name)
    if meta is not None and meta["group"] == OperatorGroup.TIME_SERIES:
        arity = len(meta["input_dims"])
        series = [c for c in node.children if c.name != "Constant"]
        return series if len(series) == arity else node.children[:arity]
    return node.children


def _collect_windows(node: ASTNode) -> List[int]:
    found = [node.window] if node.window is not None else []
    for child in _data_children(node):
        found.extend(_collect_windows(child))
    return found


def _collect_fields(node: ASTNode) -> List[str]:
    found = [node.name] if node.name in DATA_FIELD_DIMENSIONS else []
    for child in _data_children(node):
        found.extend(_collect_fields(child))
    return found


def _history_needed(node: ASTNode) -> int:
    """Bars before the last one that `node` reads: a ts_* window adds window - 1 on top of its deepest operand."""
    deepest = max((_history_needed(c) for c in _data_children(node)), default=0)
    return deepest + (node.window - 1 if node.window is not None else 0)


def mean_reversion_formula(period: int = TARGET_WINDOW, window: int = TARGET_WINDOW) -> PlantedFormula:
    """A = close - ts_mean(close, period), s = ts_zscore(A, window): a simple formula for checks."""
    tree = ASTNode(name='sub', children=[
        ASTNode(name='pv_close'),
        ASTNode(name='ts_mean', children=[ASTNode(name='pv_close')], window=period),
    ])
    return PlantedFormula(tree=tree, z_window=window, source='mean_reversion', rule='fixed')


def assert_in_search_space(engine, formula: PlantedFormula) -> None:
    """Fail loudly when the engine's scaled windows cannot express the planted formula."""
    for window in formula.windows:
        if window not in engine.scaled_periods:
            raise ValueError(f"Planted period {window} not in scaled_periods {engine.scaled_periods}")
    if formula.z_window not in engine.scaled_window_search:
        raise ValueError(f"Planted window {formula.z_window} not in scaled_window_search {engine.scaled_window_search}")


def formula_to_dict(formula: PlantedFormula) -> dict:
    def node(n: ASTNode) -> dict:
        out = {'name': n.name}
        if n.window is not None:
            out['window'] = n.window
        kids = _data_children(n)
        if kids:
            out['children'] = [node(c) for c in kids]
        return out
    return {'expression': formula.expr, 'z_window': formula.z_window, 'source_blueprint': formula.source,
            'rule': formula.rule, 'tree': node(formula.tree)}


def formula_from_dict(data: dict) -> PlantedFormula:
    def node(d: dict) -> ASTNode:
        return ASTNode(name=d['name'], children=[node(c) for c in d.get('children', [])], window=d.get('window'))
    formula = PlantedFormula(tree=node(data['tree']), z_window=int(data['z_window']),
                             source=data.get('source_blueprint', ''), rule=data.get('rule', ''))
    if formula.expr != data['expression']:
        raise ValueError(f"Stored expression {data['expression']} does not match its tree {formula.expr}")
    return formula


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


def shape_fields(bars: pd.DataFrame, formula: PlantedFormula) -> Dict[str, np.ndarray]:
    """Per-bar arrays the formula needs besides close: open_/high/low as ratios to Close, raw volume."""
    ratio_columns = {'open_': 'open_ratio', 'high': 'high_ratio', 'low': 'low_ratio'}
    out = {}
    for name in formula.used_fields:
        if name in ratio_columns:
            out[name] = bars[ratio_columns[name]].to_numpy(dtype=np.float64)
        elif name == 'volume':
            out[name] = np.nan_to_num(bars['Volume'].to_numpy(dtype=np.float64), nan=0.0)
    return out


def plant_signal(
    eps: np.ndarray,
    sigma: np.ndarray,
    first_close: float,
    beta: float,
    signal_fn: Callable[[Dict[str, np.ndarray]], float],
    lookback: int,
    shape: Optional[Dict[str, np.ndarray]] = None,
) -> PlantResult:
    """
    Sequentially add the predictable part to placebo returns `eps`.

    For each bar t the signal is computed from the reconstructed bars up to t (a trailing
    window of `lookback` bars is enough for the formula), then the next return becomes
    eps[t+1] + beta * sigma[t+1] * s_t, with NaN signals counted as 0. Index 0 carries no return.
    `sigma[i]` is the placebo return std of the segment that bar i belongs to. `shape` maps
    open_/high/low to each bar's ratio against its own Close and volume to its Volume; the window
    handed to `signal_fn` holds those fields rebuilt as in `build_ohlcv_from_returns`, plus close.
    """
    n = len(eps)
    shape = shape or {}
    returns = np.zeros(n)
    cumulative = np.ones(n)
    closes = np.empty(n)
    closes[0] = first_close
    fields = {name: np.empty(n) for name in shape}
    signal = np.full(n, np.nan)
    for t in range(n):
        for name, values in shape.items():
            fields[name][t] = values[t] if name == 'volume' else closes[t] * values[t]
        lo = max(0, t - lookback + 1)
        window = {name: arr[lo: t + 1] for name, arr in fields.items()}
        window['close'] = closes[lo: t + 1]
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
    formula: PlantedFormula,
) -> float:
    """Realized search-segment IC of the signal planted with `beta` on the placebo of `seed`."""
    perm, eps, sigma = placebo_arrays(bars, n_search, seed)
    planted = plant_signal(eps[:n_search], sigma[:n_search], first_close, beta, formula.signal_last,
                           formula.lookback, shape_fields(perm.iloc[:n_search], formula))
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
    formula: PlantedFormula,
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
    formula: PlantedFormula,
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
    planted = plant_signal(eps, sigma, first_close, beta, formula.signal_last, formula.lookback,
                           shape_fields(perm, formula))
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


def _unify_root(blueprint: ASTNode, target: ASTNode, depth: int, max_depth: int) -> bool:
    """`_unify`, plus a root `sub(x, y)` may match the target with its arguments swapped (-A is the same
    signal: the backtest tries both directions). Only the root; deeper nodes must match in order."""
    if _unify(blueprint, target, depth, max_depth):
        return True
    if blueprint.name == 'sub' and target.name == 'sub':
        b_kids, t_kids = _data_children(blueprint), _data_children(target)
        if len(b_kids) == len(t_kids) == 2:
            return (_unify(b_kids[0], t_kids[1], depth + 1, max_depth)
                    and _unify(b_kids[1], t_kids[0], depth + 1, max_depth))
    return False


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
    chooses them. A root `sub` also matches `expr` with its two arguments swapped.
    """
    body = _blueprint_body(blueprint)
    return body is not None and _unify_root(body, expr, 1, max_depth)


def is_verbatim(blueprint: ASTNode, expr: ASTNode, max_depth: int = 4) -> bool:
    """True when the blueprint already spells out `expr` with no '?' left (only windows to find)."""
    body = _blueprint_body(blueprint)
    return body is not None and not _has_hole(body) and _unify_root(body, expr, 1, max_depth)


# --------------------------------------------------------------------------- formula selection


def _nearest(target: int, allowed: Sequence[int]) -> int:
    return min(sorted(allowed), key=lambda v: abs(v - target))


def _count_slots(node: ASTNode) -> int:
    return (1 if node.name == '?' else 0) + sum(_count_slots(c) for c in _data_children(node))


def _fill_slots(node: ASTNode, period: int) -> ASTNode:
    """Copy of a blueprint body: every '?' becomes pv_close and every ts_* node gets window `period`."""
    if node.name == '?':
        return ASTNode(name=SLOT_FILL_FIELD)
    meta = OPERATOR_REGISTRY.get(node.name)
    is_ts = meta is not None and meta["group"] == OperatorGroup.TIME_SERIES
    return ASTNode(name=node.name, children=[_fill_slots(c, period) for c in _data_children(node)],
                   value=node.value, window=period if is_ts else None)


def assert_not_degenerate(formula: PlantedFormula, bars: int = 400) -> None:
    """Raise when A is constant on synthetic bars (e.g. close - close), which would plant nothing."""
    rng = np.random.default_rng(0)
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.003, bars))
    frame = pd.DataFrame({'Open': close * rng.uniform(0.998, 1.002, bars), 'High': close * rng.uniform(1.0, 1.01, bars),
                          'Low': close * rng.uniform(0.99, 1.0, bars), 'Close': close,
                          'Volume': rng.uniform(1000, 5000, bars)})
    alpha = formula.alpha_series(frame).dropna()
    if len(alpha) == 0 or float(alpha.std()) < 1e-9 * max(1.0, float(alpha.abs().max())):
        raise ValueError(f"Selected formula {formula.expr} is constant on synthetic bars; it cannot be planted")


def select_planted_formula(blueprints: Sequence[Dict[str, str]], engine) -> Tuple[PlantedFormula, Dict]:
    """
    Derive the planted formula from the frozen blueprint set (rule: FORMULA_RULE).

    Returns (formula, info); info records the window values actually used and the blueprints
    skipped because the filled formula was spelled out by one of them. Raises ValueError when no
    blueprint qualifies: the rule is never loosened.
    """
    compiler = SemanticCompiler()
    roots = [(bp['name'], compiler.compile_blueprint(bp['macro_blueprint'])) for bp in blueprints]
    period = _nearest(TARGET_WINDOW, engine.scaled_periods)
    z_window = _nearest(TARGET_WINDOW, engine.scaled_window_search)
    max_depth = getattr(engine, 'max_depth', 4)
    skipped_verbatim = []
    for name, root in roots:
        body = _blueprint_body(root)
        if body is None or _count_slots(body) < 2:
            continue
        tree = _fill_slots(body, period)
        if any(is_verbatim(other, tree, max_depth) for _, other in roots):
            skipped_verbatim.append(name)
            continue
        formula = PlantedFormula(tree=tree, z_window=z_window, source=name, rule=FORMULA_RULE)
        assert_not_degenerate(formula)
        return formula, {'period': period, 'z_window': z_window, 'skipped_verbatim': skipped_verbatim,
                         'adjusted': period != TARGET_WINDOW or z_window != TARGET_WINDOW}
    raise ValueError("No blueprint has >= 2 '?' slots under a NORMALIZED root whose filled formula is not "
                     "already spelled out by a blueprint; the rule is not loosened")


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


def _root_match_direction(cand, target, periods: Sequence[int], tolerance: int) -> Optional[float]:
    """
    Direction (+1 / -1) a candidate must be traded with to equal the target signal, or None.
    Same-order match -> +1. A root `sub` with swapped arguments is -A -> -1 (same argument as `can_express`).
    """
    if _trees_match(cand, target, periods, tolerance):
        return 1.0
    if cand[0] == 'sub' and target[0] == 'sub' and len(cand[1]) == len(target[1]) == 2:
        swapped = (cand[0], (cand[1][1], cand[1][0]), cand[2])
        if _trees_match(swapped, target, periods, tolerance):
            return -1.0
    return None


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
    A root `sub` with swapped arguments is -A and counts only with direction -1; same-order needs +1.
    """
    if candidate.get('template') != 'NORMALIZED' or candidate.get('direction') not in (1.0, -1.0):
        return False
    if not _within_steps(candidate.get('window'), formula.z_window, scaled_window_search, tolerance):
        return False
    try:
        cand_tree = parse_expression(candidate['expr'])
        target_tree = parse_expression(formula.expr)
    except (ValueError, SyntaxError):
        return False
    return _root_match_direction(cand_tree, target_tree, scaled_periods, tolerance) == candidate['direction']


def spearman_abs(a: pd.Series, b: pd.Series) -> float:
    """|Spearman| between two aligned series on their jointly valid bars (0 when degenerate)."""
    valid = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(valid) < 20 or valid['a'].std() == 0.0 or valid['b'].std() == 0.0:
        return 0.0
    return abs(float(valid['a'].corr(valid['b'], method='spearman')))


def is_near_recovery(correlation: float, threshold: float = NEAR_CORRELATION) -> bool:
    return correlation >= threshold


# --------------------------------------------------------------------------- top-k portfolio


def distinct_expressions(leaderboard: List[dict]) -> List[dict]:
    """
    One entry per rendered expression, best reward first: the highest-ranked entry of each
    expression keeps its template parameters. Entries at the -10 failure value are dropped.
    """
    seen = set()
    picked = []
    for item in sorted(leaderboard, key=lambda x: x['reward'], reverse=True):
        if item['reward'] <= -10.0 or item['expr'] in seen:
            continue
        seen.add(item['expr'])
        picked.append(item)
    return picked


def top_candidates(leaderboard: List[dict], k: int = TOP_K) -> List[dict]:
    """Best `k` candidates with k different expressions that passed scoring."""
    return distinct_expressions(leaderboard)[:k]


def rank_by_validation(candidates: List[dict], validation_rewards: Sequence[float]) -> List[int]:
    """
    Indices of `candidates` ordered by validation reward, best first. Ties keep the incoming
    (train) order; the train reward itself plays no part in the ranking.
    """
    if len(candidates) != len(validation_rewards):
        raise ValueError("One validation reward per candidate is required")
    return sorted(range(len(candidates)), key=lambda i: -validation_rewards[i])


def combine_positions(positions: List[pd.Series]) -> pd.Series:
    """Equal-weight average: each of the k position series gets weight 1/k."""
    if not positions:
        raise ValueError("No positions to combine")
    k = len(positions)
    combined = positions[0] / k
    for p in positions[1:]:
        combined = combined + p / k
    return combined
