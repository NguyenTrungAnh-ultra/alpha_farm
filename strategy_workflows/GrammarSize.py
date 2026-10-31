"""
GrammarSize
===========
Exact counts of the dimension-valid formulas the MCTS grammar can build: from one open `?` root, or by
completing a blueprint. The counts follow the same rules as the search (`MCTSState.get_actions`): which
operators a slot may take at its remaining depth, which dimensions fit, no constant under a rolling
operator. Template parameters (z-score window, thresholds) are not counted.

A rolling (`ts_*`) operator multiplies the count by `windows_per_op` (the window it can take); each leaf
is one of the data fields the code generator supports, or one of `n_constants` constants where a
dimensionless leaf is allowed outside a rolling operator.
"""

from functools import lru_cache
from itertools import product
from typing import Dict, Optional

from strategy_workflows.MCTSDimensions import (
    DATA_FIELD_DIMENSIONS, OPERATOR_REGISTRY, Dimension, NUMERIC_DIMS, OperatorGroup, result_dim, slot_operators,
)
from strategy_workflows.MCTSEngine import FIELD_EXPRESSIONS, scaled_ladders
from strategy_workflows.SemanticCompiler import ASTNode
from utilities.AppConfig import MCTS_MAX_DEPTH

# Constants a RATIO leaf can take (`terminals_for_dimensions`). The window count per rolling operator defaults to
# the engine's own ladder at the timeframe: len(scaled_periods), 4 at 60m.
DEFAULT_CONSTANTS = 7
DEFAULT_TIMEFRAME = '60m'


def windows_per_operator(timeframe: str = DEFAULT_TIMEFRAME) -> int:
    return len(scaled_ladders(timeframe)[0])

Counts = Dict[Dimension, int]


def _fields_by_dimension() -> Dict[Dimension, int]:
    out: Dict[Dimension, int] = {}
    for field, dim in DATA_FIELD_DIMENSIONS.items():
        if field in FIELD_EXPRESSIONS:
            out[dim] = out.get(dim, 0) + 1
    return out


class GrammarCounter:
    """Counts completions under one setting (depth limit, windows per rolling operator, constants)."""

    def __init__(self, max_depth: int = MCTS_MAX_DEPTH, windows_per_op: Optional[int] = None,
                 n_constants: int = DEFAULT_CONSTANTS):
        self.max_depth = max_depth
        self.windows_per_op = windows_per_operator() if windows_per_op is None else windows_per_op
        self.n_constants = n_constants
        self._fields = _fields_by_dimension()
        self._slot = lru_cache(maxsize=None)(self._slot_uncached)

    def _slot_uncached(self, remaining: int, expect_boolean: bool, in_time_series: bool) -> Counts:
        """Complete subtrees for a free `?` slot with `remaining` operator levels left, by output dimension."""
        counts: Counts = {}
        if not expect_boolean:
            for dim, n in self._fields.items():
                counts[dim] = counts.get(dim, 0) + n
            if not in_time_series:
                counts[Dimension.RATIO] = counts.get(Dimension.RATIO, 0) + self.n_constants
        for op in slot_operators(expect_boolean, remaining):
            meta = OPERATOR_REGISTRY[op]
            in_ts = meta["group"] == OperatorGroup.TIME_SERIES
            child_counts = [
                self._slot(max(remaining - 1, 0), d == Dimension.BOOLEAN, in_ts) for d in meta["input_dims"]
            ]
            self._add_operator(counts, op, child_counts)
        return counts

    def _add_operator(self, counts: Counts, op: str, child_counts) -> None:
        multiplier = self.windows_per_op if OPERATOR_REGISTRY[op]["group"] == OperatorGroup.TIME_SERIES else 1
        for combo in product(*[list(c.items()) for c in child_counts]):
            out = result_dim(op, tuple(dim for dim, _ in combo))
            if out is None:
                continue
            ways = multiplier
            for _, n in combo:
                ways *= n
            counts[out] = counts.get(out, 0) + ways

    def slot_counts(self, depth: int, expect_boolean: bool = False, in_time_series: bool = False) -> Counts:
        """Completions of a free `?` placed at `depth` (the template node is depth 0), by output dimension."""
        return dict(self._slot(max(self.max_depth - depth, 0), expect_boolean, in_time_series))

    def _node(self, node: ASTNode, depth: int, in_time_series: bool, expect_boolean: bool) -> Counts:
        if node.name == "?":
            return self.slot_counts(depth, expect_boolean, in_time_series)
        if node.name in DATA_FIELD_DIMENSIONS:
            return {DATA_FIELD_DIMENSIONS[node.name]: 1}
        if node.name == "Constant":
            return {dim: 1 for dim in NUMERIC_DIMS}
        meta = OPERATOR_REGISTRY[node.name]
        in_ts = meta["group"] == OperatorGroup.TIME_SERIES
        data = [c for c in node.children if c.name != "Constant"]
        if len(data) != len(meta["input_dims"]):
            data = list(node.children)
        child_counts = [
            self._node(child, depth + 1, in_ts, expected == Dimension.BOOLEAN)
            for child, expected in zip(data, meta["input_dims"])
        ]
        counts: Counts = {}
        self._add_operator(counts, node.name, child_counts)
        return counts

    def count_blueprint(self, root: ASTNode) -> int:
        """
        Dimension-valid completions of a compiled blueprint (its root is a template node, or a BOOLEAN
        operator). A `?` is filled by any subtree that fits the depth limit and keeps the tree valid;
        fixed rolling operators in the blueprint also choose a window.
        """
        if root.name == "normalized_template":
            counts = self._node(root.children[0], 1, False, False)
            return sum(counts.get(d, 0) for d in NUMERIC_DIMS)
        if root.name == "ratio_template":
            return self._node(root.children[0], 1, False, False).get(Dimension.RATIO, 0)
        return self._node(root, 0, False, root.name == "?").get(Dimension.BOOLEAN, 0)

    def count_roots(self) -> Dict[str, int]:
        """Completions of one open `?` under each root kind: NORMALIZED, RATIO and BOOLEAN."""
        return {
            'NORMALIZED': sum(self.slot_counts(1).get(d, 0) for d in NUMERIC_DIMS),
            'RATIO': self.slot_counts(1).get(Dimension.RATIO, 0),
            'BOOLEAN': self.slot_counts(0, expect_boolean=True).get(Dimension.BOOLEAN, 0),
        }


def count_completions(root: ASTNode, max_depth: int = MCTS_MAX_DEPTH,
                      windows_per_op: Optional[int] = None, n_constants: int = DEFAULT_CONSTANTS) -> int:
    """Number of dimension-valid completions of a compiled blueprint (see `GrammarCounter.count_blueprint`)."""
    return GrammarCounter(max_depth, windows_per_op, n_constants).count_blueprint(root)


def count_grammar(max_depth: int = MCTS_MAX_DEPTH, windows_per_op: Optional[int] = None,
                  n_constants: int = DEFAULT_CONSTANTS, roots: Optional[tuple] = None) -> int:
    """
    Dimension-valid formulas of the whole grammar from one `?` root: the sum over the root kinds in `roots`
    (default: NORMALIZED, RATIO, BOOLEAN). Template parameters are not counted.
    """
    per_root = GrammarCounter(max_depth, windows_per_op, n_constants).count_roots()
    return sum(per_root[name] for name in (roots or tuple(per_root)))
