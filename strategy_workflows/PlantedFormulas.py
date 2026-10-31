"""
PlantedFormulas
===============
The four formulas A1..A4 planted for the RQ1 comparison, and how each relates to the blueprint set.

    A1  ts_zscore(pv_close, 10), planted with a negative sign (mean reversion)      1 operator
    A2  ts_mean(sub(pv_close, pv_open), 10), intraday momentum                        2 operators
    A3  random formula with exactly 1 operator, seed 1
    A4  random formula with exactly 2 operators, seed 2

A random formula is drawn with the random-search generator (`RandomSearch.generate_formula`, NORMALIZED root)
until one passes the rejection rules, each draw continuing the same seeded stream: not constant on the search
segment, |Spearman| < 0.7 with A1 and A2 on that segment, and not one of the classical shapes.
"""

import random
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

from strategy_workflows.BlueprintGeneration import structure_key
from strategy_workflows.GrammarSize import count_completions
from strategy_workflows.MCTSDimensions import TEMPLATE_NODES
from strategy_workflows.MCTSEngine import scaled_ladders
from strategy_workflows.PlantedSignal import (
    NEAR_CORRELATION, PlantedFormula, TARGET_WINDOW, can_express, formula_from_dict, formula_to_dict, is_verbatim,
    spearman_abs,
)
from strategy_workflows.RandomSearch import METHODS, count_operators, generate_formula, template_root
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler
from utilities.AppConfig import MCTS_MAX_DEPTH

TIMEFRAME = '60m'
Z_WINDOW = TARGET_WINDOW
RANDOM_FORMULA_SEEDS = {'A3': (1, 1), 'A4': (2, 2)}      # name -> (operators, seed)
MAX_DRAWS = 20_000

# Textbook indicator shapes, compared as trees with every data field alike and windows ignored; so `sub(F, F)`
# stands for close - open, high - low and the like, and `ts_corr(F, F)` for any price-volume style correlation.
CLASSICAL_SHAPES = {
    'rolling mean / sum / max / min / rank / zscore / argmax / argmin of a field': [
        f"{op}(pv_close)" for op in ('ts_mean', 'ts_sum', 'ts_max', 'ts_min', 'ts_rank', 'ts_zscore', 'ts_argmax', 'ts_argmin')],
    'difference or ratio of two fields (candle body, range, gap)': ['sub(pv_close, pv_open)', 'div(pv_close, pv_open)'],
    'rolling correlation of two fields': ['ts_corr(pv_close, pv_volume)'],
    'distance from a rolling mean / extreme': [
        'sub(pv_close, ts_mean(pv_close))', 'sub(pv_close, ts_min(pv_close))', 'sub(ts_max(pv_close), pv_close)',
        'div(pv_close, ts_mean(pv_close))'],
    'rolling mean / sum of a difference (momentum, ATR style)': ['ts_mean(sub(pv_close, pv_open))', 'ts_sum(sub(pv_close, pv_open))'],
}


def expression_of(root: ASTNode) -> ASTNode:
    """The formula under a template node (or the node itself)."""
    return root.children[0] if root.name in TEMPLATE_NODES else root


def classical_shape_keys() -> set:
    compiler = SemanticCompiler()
    return {structure_key(expression_of(compiler.compile_blueprint(text)))
            for texts in CLASSICAL_SHAPES.values() for text in texts}


def is_classical_shape(tree: ASTNode, keys: Optional[set] = None) -> bool:
    return structure_key(tree) in (keys if keys is not None else classical_shape_keys())


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


def rejection_reason(formula: PlantedFormula, frame: pd.DataFrame, references: Dict[str, PlantedFormula],
                     shape_keys: Optional[set] = None) -> Optional[str]:
    """Why a random formula cannot be A3 / A4, or None when it passes the three rules."""
    if is_constant_on(formula, frame):
        return 'constant on the search segment'
    alpha = formula.alpha_series(frame)
    for name, reference in references.items():
        correlation = spearman_abs(alpha, reference.alpha_series(frame))
        if correlation >= NEAR_CORRELATION:
            return f'|Spearman| {correlation:.2f} with {name}'
    if is_classical_shape(formula.tree, shape_keys):
        return 'classical shape'
    return None


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
    timeframe: str = TIMEFRAME,
) -> Tuple[PlantedFormula, dict]:
    """
    A3 / A4: the first draw of `random.Random(seed)` with `n_operators` operators that passes `rejection_reason`.
    Returns (formula, info); `info['rejected']` lists the passed-over candidates with their reasons.
    """
    rng = random.Random(seed)
    shape_keys = classical_shape_keys()
    rejected: List[dict] = []
    for draw in range(MAX_DRAWS):
        tree = draw_random_formula(rng, n_operators, draw, timeframe)
        if tree is None:
            continue
        formula = PlantedFormula(tree=tree, z_window=Z_WINDOW, source=name,
                                 rule=f'random, exactly {n_operators} operator(s), seed {seed}')
        reason = rejection_reason(formula, frame, references, shape_keys)
        if reason is None:
            return formula, {'n_operators': n_operators, 'seed': seed, 'draws': draw + 1, 'rejected': rejected}
        rejected.append({'expression': formula.expr, 'reason': reason})
    raise RuntimeError(f"No acceptable {n_operators}-operator formula in {MAX_DRAWS} draws of seed {seed}")


def select_rq1_formulas(frame: pd.DataFrame, timeframe: str = TIMEFRAME) -> Dict[str, Tuple[PlantedFormula, dict]]:
    """A1..A4 with their selection info; `frame` is the search segment the random formulas are checked on."""
    formulas = classical_formulas()
    out = {name: (formula, {'kind': 'classical'}) for name, formula in formulas.items()}
    for name, (n_operators, seed) in RANDOM_FORMULA_SEEDS.items():
        formula, info = select_random_formula(name, n_operators, seed, frame, formulas, timeframe)
        out[name] = (formula, {'kind': 'random', **info})
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
