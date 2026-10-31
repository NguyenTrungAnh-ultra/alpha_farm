"""
RandomSearch
============
Random baseline over the same grammar as MCTS: dimension-valid formulas drawn with "ramped half-and-half"
(genetic programming), scored by the same engine and collected in the same leaderboard.

A sample is a complete candidate tree: a template root (NORMALIZED, RATIO or BOOLEAN) filled by
`MCTSState` actions, so every choice (operators, fields, constants, rolling windows, template parameters)
comes from the set MCTS would offer at that point and the depth limit counts as in MCTS: a numeric
root sits under a template node at depth 0, so depth D allows D - 1 operator levels under it.

Ramped half-and-half: the budget is split evenly over depths 1..4; at each depth half the trees are "full"
(an operator wherever one is allowed above the depth limit) and half are "grown" (operators and leaves
equally likely). Samples cycle through the eight (depth, method) cells in a fixed order, so every prefix of the
budget already has near-equal shares.
"""

import random
from typing import Callable, List, Optional, Sequence, Tuple

from strategy_workflows.MCTSDimensions import OPERATOR_REGISTRY
from strategy_workflows.MCTSEngine import (
    MCTSEngine, MCTSState, describe_candidate, find_first_placeholder, get_node_depth,
)
from strategy_workflows.SemanticCompiler import ASTNode

DEPTHS = (1, 2, 3, 4)
METHODS = ('full', 'grow')
CELLS: Tuple[Tuple[int, str], ...] = tuple((d, m) for d in DEPTHS for m in METHODS)
TEMPLATES = ('NORMALIZED', 'RATIO', 'BOOLEAN')
MAX_ATTEMPTS = 20


def template_root(template: str) -> ASTNode:
    """A root with one open `?` under the template (a bare `?` is a BOOLEAN root)."""
    if template == 'NORMALIZED':
        return ASTNode(name='normalized_template', children=[
            ASTNode(name='?'), ASTNode(name='window', value='?'), ASTNode(name='z_score', value='?')])
    if template == 'RATIO':
        return ASTNode(name='ratio_template', children=[
            ASTNode(name='?'), ASTNode(name='threshold_upper', value='?'), ASTNode(name='threshold_lower', value='?')])
    if template == 'BOOLEAN':
        return ASTNode(name='?')
    raise ValueError(f"Unknown template: {template}")


def cell_for_index(index: int) -> Tuple[int, str]:
    """(depth, method) of the `index`-th sample: the eight cells in rotation."""
    return CELLS[index % len(CELLS)]


def is_operator(action: ASTNode) -> bool:
    return action.name in OPERATOR_REGISTRY


def generate_formula(
    rng: random.Random, template: str, depth: int, method: str,
    scaled_window_search: Sequence[int], scaled_periods: Sequence[int],
) -> ASTNode:
    """
    One complete random candidate tree (all `?`, windows and template parameters filled).

    `depth` is the depth limit of the draw (the template node is depth 0). At a `?` above that limit "full"
    takes an operator whenever one is allowed and "grow" takes any action uniformly; at the limit only leaves
    (or, for a BOOLEAN slot, a comparison of leaves) are left. Windows, z-score and thresholds are uniform
    over the lists MCTS uses. A draw that reaches a slot with no valid action is repeated.
    """
    if depth not in DEPTHS or method not in METHODS:
        raise ValueError(f"depth must be in {DEPTHS} and method in {METHODS}, got {depth}, {method}")
    for _ in range(MAX_ATTEMPTS):
        state = MCTSState(template_root(template), depth, list(scaled_window_search), list(scaled_periods))
        while not state.is_terminal():
            actions = state.get_actions()
            if not actions:
                break
            slot = find_first_placeholder(state.ast_tree)
            if slot.name == '?':
                operators = [a for a in actions if is_operator(a)]
                if method == 'full' and operators and get_node_depth(state.ast_tree, slot) < depth:
                    actions = operators
            state = state.apply_action(rng.choice(actions))
        else:
            return state.ast_tree
    raise RuntimeError(f"No complete {template} formula of depth {depth} after {MAX_ATTEMPTS} attempts")


def count_operators(node: ASTNode) -> int:
    return (1 if node.name in OPERATOR_REGISTRY else 0) + sum(count_operators(c) for c in node.children)


def random_search(
    engine: MCTSEngine, total: int, chunk: int, on_chunk: Optional[Callable[[int], None]] = None,
) -> dict:
    """
    Draw `total` formulas with `engine.rng`, score them with `engine.evaluate_expression` and add them to
    `engine.leaderboard`. A formula already scored (same expression and template parameters) is skipped but
    still counts against the budget. `on_chunk(n)` is called after every `chunk` samples (and for the remainder
    at the end) with the number of samples since the last call.
    Returns counts: samples, duplicates, and the number of samples per depth.
    """
    seen = set()
    reported = 0
    duplicates = 0
    per_depth = {d: 0 for d in DEPTHS}
    window_search, periods = engine.scaled_window_search, engine.scaled_periods
    for index in range(total):
        depth, method = cell_for_index(index)
        per_depth[depth] += 1
        tree = generate_formula(engine.rng, engine.rng.choice(TEMPLATES), depth, method, window_search, periods)
        desc = describe_candidate(tree)
        if desc['cache_key'] in seen:
            duplicates += 1
        else:
            seen.add(desc['cache_key'])
            reward, direction, metrics = engine.evaluate_expression(tree)
            engine.update_leaderboard(desc['expr'], reward, direction, metrics)
        done = index + 1
        if done % chunk == 0 or done == total:
            if on_chunk is not None:
                on_chunk(done - reported)
            reported = done
    return {'samples': total, 'duplicates': duplicates, 'per_depth': per_depth}
