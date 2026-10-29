import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

"""
MCTSDimensions
==============
Defines the syntax router and dimensional constraints for the Unified Compiler Architecture.

It provides type enumerations for formula dimensions and operator groups, maps standard
data fields to their respective dimensions, specifies the input/output signatures of all
supported operators in the system, and implements backward chaining helpers for tree expansion.
"""


from enum import Enum, auto
from functools import lru_cache
from itertools import product
from typing import Dict, FrozenSet, List, Optional

class Dimension(Enum):
    """
    Represents the physical or mathematical unit of measurement/scale for a formula node.
    """
    CURRENCY = auto()   # Prices
    VOLUME = auto()     # Volume
    RATIO = auto()      # Dimensionless, percentages (returns, correlations, z-scores)
    BOOLEAN = auto()    # True/False signals
    ANY = auto()        # Wildcard: unresolved slot, constant, or output that depends on the inputs (see result_dim)

class TemplateType(Enum):
    BOOLEAN = auto()
    RATIO = auto()
    NORMALIZED = auto()

DIMENSION_TO_TEMPLATE = {
    Dimension.BOOLEAN: TemplateType.BOOLEAN,
    Dimension.RATIO: TemplateType.RATIO,
    Dimension.ANY: TemplateType.NORMALIZED,
    Dimension.CURRENCY: TemplateType.NORMALIZED,
    Dimension.VOLUME: TemplateType.NORMALIZED,
}

class OperatorGroup(Enum):
    """
    Categorizes operators based on their mathematical or indicator family.
    """
    TIME_SERIES = auto()
    LOGIC = auto()
    STATISTICS = auto()

DATA_FIELD_DIMENSIONS = {
    "pv_open": Dimension.CURRENCY,
    "pv_high": Dimension.CURRENCY,
    "pv_low": Dimension.CURRENCY,
    "pv_close": Dimension.CURRENCY,
    "pv_volume": Dimension.VOLUME,
    "pv_vn30_close": Dimension.CURRENCY,
}

OPERATOR_REGISTRY = {
    # 1. TIME-SERIES (Alpha Primitives)
    "ts_mean": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "ts_sum": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "ts_max": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "ts_min": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "ts_rank": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.RATIO},
    "ts_corr": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.RATIO},
    "ts_zscore": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.RATIO},
    "ts_argmax": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "ts_argmin": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    
    # 2. LOGIC
    "crossed": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.BOOLEAN},
    "crossed_above": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.BOOLEAN},
    "crossed_below": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.BOOLEAN},
    "rising": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY], "output_dim": Dimension.BOOLEAN},
    "falling": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY], "output_dim": Dimension.BOOLEAN},
    "between": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY], "output_dim": Dimension.BOOLEAN},
    "and_": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.BOOLEAN, Dimension.BOOLEAN], "output_dim": Dimension.BOOLEAN},
    "or_": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.BOOLEAN, Dimension.BOOLEAN], "output_dim": Dimension.BOOLEAN},
    "not_": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.BOOLEAN], "output_dim": Dimension.BOOLEAN},
    "greater_than": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.BOOLEAN},
    "less_than": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.BOOLEAN},
    "equal": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.BOOLEAN},

    # 3. STATISTICS & MATH
    "add": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.ANY},
    "sub": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.ANY},
    "mult": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.ANY},
    "div": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.RATIO},
}

# Registered for type checking, but no code is generated for them yet: MCTS never proposes
# them and the prompt never lists them.
UNIMPLEMENTED_OPERATORS = frozenset({
    "crossed", "crossed_above", "crossed_below", "rising", "falling", "between",
})

# ─── Dimension inference ──────────────────────────────────────────────────────────────────
# A node does not have one dimension but a set of dimensions it can still take: a data field has
# exactly one, a `?` slot has every dimension some completion can produce, an operator has the
# outputs `result_dim` allows for the combinations of its inputs. Every `?` appears once, so
# subtrees are independent and the set propagation below is exact (no false accepts or rejects).
# In OPERATOR_REGISTRY, `output_dim` is the declared kind (it picks the position template);
# `result_dim` is the dimension rule actually applied to a tree.

NUMERIC_DIMS = frozenset({Dimension.CURRENCY, Dimension.VOLUME, Dimension.RATIO})
BOOLEAN_DIMS = frozenset({Dimension.BOOLEAN})

# Operators whose inputs must share one dimension (reported as "Dimensional Bleeding").
SAME_DIM_OPERATORS = frozenset({
    "add", "sub", "crossed", "crossed_above", "crossed_below", "greater_than", "less_than", "equal",
})
_COMPARISONS = frozenset({
    "crossed", "crossed_above", "crossed_below", "greater_than", "less_than", "equal",
})
TEMPLATE_NODES = ("normalized_template", "ratio_template")

# Deepest operator nesting assumed when no max_depth is given (compile time). Sets stop growing
# after two or three levels, so any value above that gives the same answer.
UNBOUNDED_DEPTH = 6


def result_dim(op: str, dims) -> Optional[Dimension]:
    """
    Output dimension of `op` for concrete (never ANY) input dimensions, or None if the
    combination is invalid.

    ts_mean/sum/max/min, add, sub keep the input dimension. ts_rank/zscore/argmax/argmin/corr,
    and a division of equal dimensions, are dimensionless (RATIO). `mult` needs a RATIO side and
    `div` a RATIO divisor or equal dimensions: the enum has no compound dimension, so
    CURRENCY x VOLUME or RATIO / CURRENCY cannot be represented and are rejected.
    """
    meta = OPERATOR_REGISTRY[op]
    for expected, d in zip(meta["input_dims"], dims):
        if (d == Dimension.BOOLEAN) != (expected == Dimension.BOOLEAN):
            return None
    if op in ("ts_argmax", "ts_argmin", "ts_rank", "ts_zscore", "ts_corr"):
        return Dimension.RATIO
    if op in ("add", "sub"):
        return dims[0] if dims[0] == dims[1] else None
    if op == "mult":
        if dims[0] == Dimension.RATIO:
            return dims[1]
        return dims[0] if dims[1] == Dimension.RATIO else None
    if op == "div":
        if dims[0] == dims[1]:
            return Dimension.RATIO
        return dims[0] if dims[1] == Dimension.RATIO else None
    if op in _COMPARISONS and dims[0] != dims[1]:
        return None
    if meta["output_dim"] == Dimension.ANY:
        return dims[0]
    return meta["output_dim"]


def operator_output_dims(op: str, child_sets) -> FrozenSet[Dimension]:
    """Dimensions `op` can output when its inputs can take the given sets (empty = impossible)."""
    outs = set()
    for combo in product(*child_sets):
        out = result_dim(op, combo)
        if out is not None:
            outs.add(out)
    return frozenset(outs)


def terminal_dims(expect_boolean: bool, in_time_series: bool) -> FrozenSet[Dimension]:
    """Dimensions a leaf (data field or constant) can fill. A rolling operator takes no constant."""
    if expect_boolean:
        return frozenset()
    dims = set(DATA_FIELD_DIMENSIONS.values())
    if not in_time_series:
        dims.add(Dimension.RATIO)
    return frozenset(dims)


def slot_operators(expect_boolean: bool, remaining: int) -> List[str]:
    """
    Implemented operators MCTS may put into a slot: BOOLEAN-returning ones for a BOOLEAN slot,
    numeric ones otherwise. With no depth left only a BOOLEAN slot still takes an operator, and
    only one without BOOLEAN inputs (a comparison of two leaves), since no leaf is BOOLEAN.
    """
    ops = []
    for op, meta in OPERATOR_REGISTRY.items():
        if op in UNIMPLEMENTED_OPERATORS:
            continue
        if (meta["output_dim"] == Dimension.BOOLEAN) != expect_boolean:
            continue
        if remaining <= 0 and (not expect_boolean or Dimension.BOOLEAN in meta["input_dims"]):
            continue
        ops.append(op)
    return ops


def _child_hole_dims(op: str, remaining: int) -> List[FrozenSet[Dimension]]:
    meta = OPERATOR_REGISTRY[op]
    in_ts = meta["group"] == OperatorGroup.TIME_SERIES
    return [hole_dims(max(remaining - 1, 0), d == Dimension.BOOLEAN, in_ts) for d in meta["input_dims"]]


@lru_cache(maxsize=None)
def hole_dims(remaining: int, expect_boolean: bool, in_time_series: bool) -> FrozenSet[Dimension]:
    """
    Dimensions an unconstrained `?` slot can end up with, given `remaining` operator levels
    below it: its leaves plus what the operators allowed there can output.
    """
    dims = set(terminal_dims(expect_boolean, in_time_series))
    for op in slot_operators(expect_boolean, remaining):
        dims |= operator_output_dims(op, _child_hole_dims(op, remaining))
    return frozenset(dims)


def operators_for_slot(allowed, remaining: int, expect_boolean: bool) -> List[str]:
    """Operators for a slot that must take a dimension in `allowed`, so the whole tree stays valid."""
    return [
        op for op in slot_operators(expect_boolean, remaining)
        if operator_output_dims(op, _child_hole_dims(op, remaining)) & allowed
    ]


class DimensionAnalysis:
    """
    Result of `analyze_dimensions`.

    root_dims: dimensions the tree can take (empty on error).
    slot_dims: id(`?` node) -> dimensions that slot can take so the whole tree stays valid.
    error: message of the first invalid node, or None.
    """
    def __init__(self):
        self.root_dims: FrozenSet[Dimension] = frozenset()
        self.slot_dims: Dict[int, FrozenSet[Dimension]] = {}
        self.error: Optional[str] = None


def _fmt(dims) -> str:
    return "{" + "|".join(sorted(d.name for d in dims)) + "}"


def _data_children(node):
    """Series arguments of an operator node: constants are not arguments unless arity needs them."""
    arity = len(OPERATOR_REGISTRY[node.name]["input_dims"])
    series = [c for c in node.children if c.name != "Constant"]
    if len(series) == arity:
        return series, None
    if len(node.children) == arity:
        return list(node.children), None
    return None, f"Arity mismatch for {node.name}: expected {arity} data args, got {len(series)}"


def _invalid_combination_message(node, child_sets) -> str:
    meta = OPERATOR_REGISTRY[node.name]
    for expected, got in zip(meta["input_dims"], child_sets):
        want = BOOLEAN_DIMS if expected == Dimension.BOOLEAN else NUMERIC_DIMS
        if not (got & want):
            kind = "BOOLEAN" if expected == Dimension.BOOLEAN else "a numeric series"
            return f"Dimension mismatch in {node.name}: expected {kind}, got {_fmt(got)}"
    shown = " vs ".join(_fmt(s) for s in child_sets)
    if node.name in SAME_DIM_OPERATORS:
        return (f"Dimensional Bleeding in {node.name}: inputs have incompatible dimensions {shown} "
                "(they must share one dimension)")
    if node.name == "mult":
        return (f"Dimension mismatch in mult: {shown} has no valid product "
                "(one side must be a dimensionless RATIO)")
    if node.name == "div":
        return (f"Dimension mismatch in div: {shown} has no valid quotient "
                "(equal dimensions, or a RATIO divisor)")
    return f"Dimension mismatch in {node.name}: inputs {shown} are not valid"


def analyze_dimensions(root, max_depth: Optional[int] = None) -> DimensionAnalysis:
    """
    Check a tree's dimensions and work out which dimensions each `?` slot can take.

    `root` is any node with `.name` and `.children` (an ASTNode, possibly wrapped in a
    normalized_template / ratio_template). Bottom-up pass: set of reachable dimensions per node,
    first invalid node recorded in `error`. Top-down pass: for each slot, the dimensions that
    still allow the rest of the tree to be valid. `max_depth` (None = unbounded) is the MCTS
    depth limit, which bounds what a slot can still grow into.
    """
    result = DimensionAnalysis()
    limit = UNBOUNDED_DEPTH if max_depth is None else max_depth
    info = {}   # id(node) -> (data children, child sets)

    def fail(message):
        result.error = result.error or message
        return frozenset()

    def up(node, depth, expect_boolean, in_ts) -> FrozenSet[Dimension]:
        name = node.name
        if name == "?":
            s = hole_dims(max(limit - depth, 0), expect_boolean, in_ts)
            info[id(node)] = ([], [])
            return s
        if name == "Constant":
            return NUMERIC_DIMS
        if name in DATA_FIELD_DIMENSIONS:
            return frozenset({DATA_FIELD_DIMENSIONS[name]})
        if name in TEMPLATE_NODES:
            s = up(node.children[0], depth + 1, False, False)
            info[id(node)] = ([node.children[0]], [s])
            return s
        if name not in OPERATOR_REGISTRY:
            return fail(f"Unknown operator: {name}")
        meta = OPERATOR_REGISTRY[name]
        data, arity_error = _data_children(node)
        if arity_error:
            return fail(arity_error)
        in_ts_child = meta["group"] == OperatorGroup.TIME_SERIES
        child_sets = [
            up(c, depth + 1, expected == Dimension.BOOLEAN, in_ts_child)
            for c, expected in zip(data, meta["input_dims"])
        ]
        info[id(node)] = (data, child_sets)
        if not all(child_sets):
            return frozenset()
        s = operator_output_dims(name, child_sets)
        if not s:
            fail(_invalid_combination_message(node, child_sets))
        return s

    root_set = up(root, 0, False, False)
    if result.error or not root_set:
        result.error = result.error or "Tree has no valid dimension"
        return result
    if root.name == "ratio_template":
        required_root = root_set & frozenset({Dimension.RATIO})
        if not required_root:
            result.error = f"ratio_template needs a RATIO child, got {_fmt(root_set)}"
            return result
    else:
        required_root = root_set
    result.root_dims = root_set

    def down(node, required):
        if id(node) not in info:
            return
        data, child_sets = info[id(node)]
        if node.name == "?":
            result.slot_dims[id(node)] = required
        elif node.name in TEMPLATE_NODES:
            down(data[0], required)
        else:
            for i, child in enumerate(data):
                allowed = set()
                for d in child_sets[i]:
                    others = [child_sets[j] if j != i else frozenset({d}) for j in range(len(data))]
                    if operator_output_dims(node.name, others) & required:
                        allowed.add(d)
                down(child, frozenset(allowed))

    down(root, required_root)
    return result
