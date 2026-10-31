"""
PlantedFormulas
===============
The four formulas A1..A4 planted for the RQ1 comparison, and how each relates to the blueprint set.

    A1  ts_zscore(pv_close, 10), planted with a negative sign (mean reversion)      1 operator
    A2  ts_mean(sub(pv_close, pv_open), 10), intraday momentum                        2 operators
    A3  random formula with exactly 1 operator, seed 1
    A4  random formula with exactly 2 operators, seed 2

A random formula is drawn with the random-search generator (`RandomSearch.generate_formula`, NORMALIZED root)
until one passes the rejection rules, each draw continuing the same seeded stream. On the search segment:
    1. not constant, and |Spearman| < 0.7 with A1 and with A2;
    2. not the tree shape of A1 or A2 (data fields and windows ignored);
    3. contains a rolling `ts_*` operator;
    4. stationary: augmented Dickey-Fuller p < 0.05 on its raw values;
    5. not crowded: fewer than 1% of the valid formulas of a fixed random-search sample (`CrowdingSample`) have
       |Spearman| >= 0.7 with it, i.e. an arbitrary formula rarely counts as a near recovery by accident.
Rules 4 and 5 are only checked on A1 and A2, never used to replace them (`ClassicalCheckFailed`).
"""

import random
import warnings
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from statsmodels.tsa.stattools import adfuller

from core_engine.AlphaEngine import AlphaDataProxy
from strategy_workflows.BlueprintGeneration import structure_key
from strategy_workflows.GrammarSize import count_completions
from strategy_workflows.MCTSDimensions import TEMPLATE_NODES
from strategy_workflows.MCTSEngine import describe_candidate, evaluate_alpha, scaled_ladders
from strategy_workflows.PlantedSignal import (
    NEAR_CORRELATION, PlantedFormula, TARGET_WINDOW, can_express, formula_from_dict, formula_to_dict, is_verbatim,
    spearman_abs,
)
from strategy_workflows.RandomSearch import (
    METHODS, TEMPLATES, cell_for_index, count_operators, generate_formula, template_root,
)
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler
from utilities.AppConfig import MCTS_MAX_DEPTH

TIMEFRAME = '60m'
Z_WINDOW = TARGET_WINDOW
RANDOM_FORMULA_SEEDS = {'A3': (1, 1), 'A4': (2, 2)}      # name -> (operators, seed)
MAX_DRAWS = 20_000
ADF_ALPHA = 0.05
CROWDING_SAMPLES = 10_000
CROWDING_SEED = 2026
CROWDING_LIMIT = 0.01
MIN_OVERLAP = 20                                          # bars two series need in common to be compared


class ClassicalCheckFailed(RuntimeError):
    """A1 or A2 fails the stationarity or crowding check; the user decides what replaces it."""


def expression_of(root: ASTNode) -> ASTNode:
    """The formula under a template node (or the node itself)."""
    return root.children[0] if root.name in TEMPLATE_NODES else root


def shape_keys(references: Dict[str, PlantedFormula]) -> set:
    """Tree shapes (every data field alike, windows ignored) of the reference formulas."""
    return {structure_key(reference.tree) for reference in references.values()}


def has_rolling_operator(tree: ASTNode) -> bool:
    return tree.name.startswith('ts_') or any(has_rolling_operator(child) for child in tree.children)


def _node(name: str, window: Optional[int] = None, children: Sequence[ASTNode] = ()) -> ASTNode:
    return ASTNode(name=name, children=list(children), window=window)


def classical_formulas() -> Dict[str, PlantedFormula]:
    a1 = PlantedFormula(tree=_node('ts_zscore', TARGET_WINDOW, [_node('pv_close')]), z_window=Z_WINDOW,
                        source='A1', rule='classical mean reversion, planted with sign -1', sign=-1.0)
    a2 = PlantedFormula(tree=_node('ts_mean', TARGET_WINDOW, [_node('sub', None, [_node('pv_close'), _node('pv_open')])]),
                        z_window=Z_WINDOW, source='A2', rule='classical intraday momentum')
    return {'A1': a1, 'A2': a2}


def is_constant_on(formula: PlantedFormula, frame: pd.DataFrame) -> bool:
    """True when A has no variation on `frame`: no data field, not a series, all NaN, or a standard deviation of zero."""
    if not formula.used_fields:
        return True
    try:
        alpha = formula.alpha_series(frame).dropna()
    except TypeError:
        return True
    return len(alpha) == 0 or float(alpha.std()) < 1e-9 * max(1.0, float(alpha.abs().max()))


def adf_p_value(alpha: pd.Series) -> float:
    """Augmented Dickey-Fuller p-value (AIC lag choice) of the finite values; NaN when the test cannot run."""
    values = alpha.replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return float(adfuller(values, autolag='AIC')[1])
    except (ValueError, np.linalg.LinAlgError):
        return float('nan')


def is_stationary(p_value: float) -> bool:
    return bool(p_value < ADF_ALPHA)


class CrowdingSample:
    """
    A fixed random-search sample evaluated on one frame: `n_drawn` formulas drawn like `random_search` does
    (seeded stream, depths in rotation, random template), of which `n_valid` evaluate to a non-constant series.
    `share(alpha)` is the fraction of the valid ones with |Spearman| >= NEAR_CORRELATION with `alpha`, the chance
    that an arbitrary formula counts as a near recovery of it by accident. Values are kept as float32 rows.
    """

    def __init__(self, frame: pd.DataFrame, n_drawn: Optional[int] = None, seed: int = CROWDING_SEED,
                 timeframe: str = TIMEFRAME):
        n_drawn = CROWDING_SAMPLES if n_drawn is None else n_drawn
        periods, windows = scaled_ladders(timeframe)
        proxy = AlphaDataProxy(frame)
        rng = random.Random(seed)
        self.index = frame.index
        self.n_drawn = n_drawn
        rows = []
        with warnings.catch_warnings(), np.errstate(all='ignore'):
            warnings.simplefilter('ignore')
            for i in range(n_drawn):
                depth, method = cell_for_index(i)
                tree = generate_formula(rng, rng.choice(TEMPLATES), depth, method, windows, periods)
                try:
                    values = evaluate_alpha(describe_candidate(tree)['expr'], proxy)
                    values = values.reindex(frame.index).to_numpy(dtype=np.float32)
                except Exception:
                    continue
                finite = values[np.isfinite(values)]
                if len(finite) < MIN_OVERLAP or float(finite.std()) < 1e-9 * max(1.0, float(np.abs(finite).max())):
                    continue
                rows.append(values)
        self.values = np.vstack(rows) if rows else np.empty((0, len(frame)), dtype=np.float32)
        self.n_valid = len(self.values)

    def share(self, alpha: pd.Series) -> float:
        """Share of the valid sample near `alpha`; NaN when the sample has no valid formula."""
        if self.n_valid == 0:
            return float('nan')
        target = alpha.reindex(self.index).to_numpy(dtype=np.float32)
        target_ok = ~np.isnan(target)
        hits = 0
        for row in self.values:
            both = target_ok & ~np.isnan(row)
            if both.sum() < MIN_OVERLAP:
                continue
            a, b = rankdata(row[both]), rankdata(target[both])
            if a.std() == 0.0 or b.std() == 0.0:
                continue
            hits += abs(float(np.corrcoef(a, b)[0, 1])) >= NEAR_CORRELATION
        return hits / self.n_valid


def check_formula(formula: PlantedFormula, frame: pd.DataFrame, references: Dict[str, PlantedFormula],
                  crowd: Optional[CrowdingSample] = None) -> Tuple[Optional[str], dict]:
    """
    The five rules for a random formula, cheapest first. Returns (reason, stats): reason is None when all pass,
    stats holds `adf_p` / `crowding_share` for the rules reached.
    """
    stats: dict = {}
    if is_constant_on(formula, frame):
        return 'constant on the search segment', stats
    alpha = formula.alpha_series(frame)
    for name, reference in references.items():
        correlation = spearman_abs(alpha, reference.alpha_series(frame))
        if correlation >= NEAR_CORRELATION:
            return f'|Spearman| {correlation:.2f} with {name}', stats
    if structure_key(formula.tree) in shape_keys(references):
        return 'same tree shape as A1 or A2', stats
    if not has_rolling_operator(formula.tree):
        return 'no rolling ts_ operator', stats
    stats['adf_p'] = adf_p_value(alpha)
    if not is_stationary(stats['adf_p']):
        return f"not stationary (ADF p {stats['adf_p']:.3f})", stats
    if crowd is not None:
        stats['crowding_share'] = crowd.share(alpha)
        if not stats['crowding_share'] < CROWDING_LIMIT:
            return f"crowded ({stats['crowding_share']:.2%} of the random sample is near)", stats
    return None, stats


def rejection_reason(formula: PlantedFormula, frame: pd.DataFrame, references: Dict[str, PlantedFormula],
                     crowd: Optional[CrowdingSample] = None) -> Optional[str]:
    return check_formula(formula, frame, references, crowd)[0]


def draw_random_formula(rng: random.Random, n_operators: int, draw: int, timeframe: str = TIMEFRAME) -> Optional[ASTNode]:
    """
    One candidate expression with exactly `n_operators` operators, or None when the draw has another count.
    The generator runs at depth `n_operators + 1` (a chain of that many operators needs that depth), alternating
    full and grown trees, under a NORMALIZED root.
    """
    periods, windows = scaled_ladders(timeframe)
    root = generate_formula(rng, 'NORMALIZED', n_operators + 1, METHODS[draw % 2], windows, periods)
    expression = expression_of(root)
    return expression if count_operators(expression) == n_operators else None


def select_random_formula(
    name: str, n_operators: int, seed: int, frame: pd.DataFrame, references: Dict[str, PlantedFormula],
    timeframe: str = TIMEFRAME, crowd: Optional[CrowdingSample] = None,
) -> Tuple[PlantedFormula, dict]:
    """
    A3 / A4: the first draw of `random.Random(seed)` with `n_operators` operators that passes `check_formula`.
    `crowd` is built here when not given. Returns (formula, info); `info['rejected']` lists the passed-over
    candidates with their reasons, `info['candidates']` how many were checked (the accepted one included).
    """
    rng = random.Random(seed)
    crowd = crowd if crowd is not None else CrowdingSample(frame, timeframe=timeframe)
    rejected: List[dict] = []
    for draw in range(MAX_DRAWS):
        tree = draw_random_formula(rng, n_operators, draw, timeframe)
        if tree is None:
            continue
        formula = PlantedFormula(tree=tree, z_window=Z_WINDOW, source=name,
                                 rule=f'random, exactly {n_operators} operator(s), seed {seed}')
        reason, stats = check_formula(formula, frame, references, crowd)
        if reason is None:
            return formula, {'n_operators': n_operators, 'seed': seed, 'draws': draw + 1,
                             'candidates': len(rejected) + 1, **stats, 'rejected': rejected}
        rejected.append({'expression': formula.expr, 'reason': reason, **stats})
    raise RuntimeError(f"No acceptable {n_operators}-operator formula in {MAX_DRAWS} draws of seed {seed}")


def check_classical_formulas(formulas: Dict[str, PlantedFormula], frame: pd.DataFrame,
                             crowd: CrowdingSample) -> Dict[str, dict]:
    """
    Stationarity and crowding of A1 / A2: reported, never repaired. Computes both, then raises
    `ClassicalCheckFailed` naming every failure.
    """
    stats, failures = {}, []
    for name, formula in formulas.items():
        alpha = formula.alpha_series(frame)
        stats[name] = {'adf_p': adf_p_value(alpha), 'crowding_share': crowd.share(alpha)}
        if not is_stationary(stats[name]['adf_p']):
            failures.append(f"{name} is not stationary (ADF p {stats[name]['adf_p']:.3f} >= {ADF_ALPHA})")
        if not stats[name]['crowding_share'] < CROWDING_LIMIT:
            failures.append(f"{name} is crowded ({stats[name]['crowding_share']:.2%} of the random sample is within "
                            f"|Spearman| {NEAR_CORRELATION}; limit {CROWDING_LIMIT:.0%})")
    if failures:
        raise ClassicalCheckFailed("; ".join(failures) + f". Checks: {stats}")
    return stats


def select_rq1_formulas(frame: pd.DataFrame, timeframe: str = TIMEFRAME,
                        crowd: Optional[CrowdingSample] = None) -> Dict[str, Tuple[PlantedFormula, dict]]:
    """
    A1..A4 with their selection info; `frame` is the search segment the checks run on. One crowding sample
    serves all four. Raises `ClassicalCheckFailed` when A1 or A2 is non-stationary or crowded.
    """
    formulas = classical_formulas()
    crowd = crowd if crowd is not None else CrowdingSample(frame, timeframe=timeframe)
    sample = {'crowding_drawn': crowd.n_drawn, 'crowding_valid': crowd.n_valid}
    checks = check_classical_formulas(formulas, frame, crowd)
    out = {name: (formula, {'kind': 'classical', **checks[name], **sample}) for name, formula in formulas.items()}
    for name, (n_operators, seed) in RANDOM_FORMULA_SEEDS.items():
        formula, info = select_random_formula(name, n_operators, seed, frame, formulas, timeframe, crowd)
        out[name] = (formula, {'kind': 'random', **info, **sample})
    return out


# --------------------------------------------------------------------------- region of the blueprint set


def fits_depth_limit(formula: PlantedFormula, max_depth: int = MCTS_MAX_DEPTH) -> bool:
    """True when the search can build A from a lone `?` under a NORMALIZED template within `max_depth`."""
    return can_express(template_root('NORMALIZED'), formula.tree, max_depth)


def coverage_report(blueprints: Sequence[Dict[str, str]], formula: PlantedFormula,
                    max_depth: int = MCTS_MAX_DEPTH) -> dict:
    """
    Which blueprints can fill in to A (`can_express`), which already spell it out (`is_verbatim`), the number of
    dimension-valid completions of each expressing blueprint and the smallest of those (the difficulty of finding
    A inside its region). `in_region` is False when no blueprint expresses A: the search can only reach it
    through the feedback round, or not at all.
    """
    compiler = SemanticCompiler()
    expressing, verbatim, completions = [], [], {}
    for bp in blueprints:
        root = compiler.compile_blueprint(bp['macro_blueprint'])
        if is_verbatim(root, formula.tree, max_depth):
            verbatim.append(bp['name'])
        if can_express(root, formula.tree, max_depth):
            expressing.append(bp['name'])
            completions[bp['name']] = count_completions(root, max_depth)
    smallest = min(completions, key=lambda name: completions[name]) if completions else None
    return {
        'fits_depth_limit': fits_depth_limit(formula, max_depth), 'in_region': bool(expressing),
        'expressing': expressing, 'verbatim': verbatim, 'completions': completions,
        'smallest': None if smallest is None else {'name': smallest, 'completions': completions[smallest]},
    }


# --------------------------------------------------------------------------- storage


def formulas_to_dict(selected: Dict[str, Tuple[PlantedFormula, dict]]) -> dict:
    return {name: {**formula_to_dict(formula), 'selection': info} for name, (formula, info) in selected.items()}


def formulas_from_dict(data: dict) -> Dict[str, PlantedFormula]:
    return {name: formula_from_dict(item) for name, item in data.items()}
