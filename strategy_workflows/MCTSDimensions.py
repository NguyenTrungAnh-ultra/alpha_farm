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

class Dimension(Enum):
    """
    Represents the physical or mathematical unit of measurement/scale for a formula node.
    """
    CURRENCY = auto()   # Prices
    VOLUME = auto()     # Volume
    RATIO = auto()      # Dimensionless, percentages (returns, correlations, z-scores)
    BOOLEAN = auto()    # True/False signals
    ANY = auto()        # Can be anything, preserves input dimension

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

def get_operators_by_return_dim(target_dim: Dimension):
    """
    Perform backward chaining to find all operators returning a target dimension.
    """
    ops = []
    for op, meta in OPERATOR_REGISTRY.items():
        if meta["output_dim"] == target_dim or meta["output_dim"] == Dimension.ANY:
            ops.append(op)
    return ops
