import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Syntax Router & Dimensional Constraints for Unified Compiler Architecture

from enum import Enum, auto

class Dimension(Enum):
    CURRENCY = auto()   # Prices
    VOLUME = auto()     # Volume
    RATIO = auto()      # Dimensionless, percentages (RSI, returns)
    TIME = auto()       # Time periods
    BOOLEAN = auto()    # True/False signals
    ANY = auto()        # Can be anything, preserves input dimension

class OperatorGroup(Enum):
    TIME_SERIES = auto()
    LOGIC = auto()
    OVERLAP = auto()
    OSCILLATOR = auto()
    STATISTICS = auto()
    CANDLESTICK = auto()

DATA_FIELD_DIMENSIONS = {
    "pv_open": Dimension.CURRENCY,
    "pv_high": Dimension.CURRENCY,
    "pv_low": Dimension.CURRENCY,
    "pv_close": Dimension.CURRENCY,
    "pv_volume": Dimension.VOLUME,
    "pv_vn30_close": Dimension.CURRENCY,
}

# The registry defines every operator, its group, arity (number of children),
# its input signature (what dimensions it expects), and output dimension.
# Arity is derived from the length of input_dims. Constant parameters (like window size) are ignored for Arity.
OPERATOR_REGISTRY = {
    # 1. TIME-SERIES
    "shift": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "diff": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "pct_change": {"group": OperatorGroup.TIME_SERIES, "input_dims": [Dimension.ANY], "output_dim": Dimension.RATIO},
    
    "crossed": {"group": OperatorGroup.LOGIC, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.BOOLEAN}, # Special check: inputs must match
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

    # 3. OVERLAP (Preserves dimension, heavily pruned to avoid Illusion of Diversity)
    "ema": {"group": OperatorGroup.OVERLAP, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "vwap": {"group": OperatorGroup.OVERLAP, "input_dims": [], "output_dim": Dimension.CURRENCY}, # Arity 0, expects h, l, c, v internally
    "bbands_upper": {"group": OperatorGroup.OVERLAP, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "bbands_middle": {"group": OperatorGroup.OVERLAP, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "bbands_lower": {"group": OperatorGroup.OVERLAP, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},

    # 4. OSCILLATORS
    "rsi": {"group": OperatorGroup.OSCILLATOR, "input_dims": [Dimension.ANY], "output_dim": Dimension.RATIO},
    "macd_line": {"group": OperatorGroup.OSCILLATOR, "input_dims": [Dimension.CURRENCY], "output_dim": Dimension.CURRENCY},
    "macd_signal": {"group": OperatorGroup.OSCILLATOR, "input_dims": [Dimension.CURRENCY], "output_dim": Dimension.CURRENCY},
    "macd_hist": {"group": OperatorGroup.OSCILLATOR, "input_dims": [Dimension.CURRENCY], "output_dim": Dimension.CURRENCY},
    "adx": {"group": OperatorGroup.OSCILLATOR, "input_dims": [], "output_dim": Dimension.RATIO}, # Arity 0, expects h, l, c internally
    "stoch_k": {"group": OperatorGroup.OSCILLATOR, "input_dims": [], "output_dim": Dimension.RATIO}, # Arity 0, expects h, l, c internally
    "stoch_d": {"group": OperatorGroup.OSCILLATOR, "input_dims": [], "output_dim": Dimension.RATIO}, # Arity 0, expects h, l, c internally

    # 5. STATISTICS & MATH
    "stddev": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "var": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY], "output_dim": Dimension.ANY},
    "zscore": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY], "output_dim": Dimension.RATIO},
    "add": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.ANY},
    "sub": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.ANY},
    "mult": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.ANY},
    "div": {"group": OperatorGroup.STATISTICS, "input_dims": [Dimension.ANY, Dimension.ANY], "output_dim": Dimension.RATIO},

    # 6. CANDLESTICK (Leaf Features) - Arity 0, no child nodes allowed!
    "doji": {"group": OperatorGroup.CANDLESTICK, "input_dims": [], "output_dim": Dimension.BOOLEAN},
    "hammer": {"group": OperatorGroup.CANDLESTICK, "input_dims": [], "output_dim": Dimension.BOOLEAN},
    "three_black_crows": {"group": OperatorGroup.CANDLESTICK, "input_dims": [], "output_dim": Dimension.BOOLEAN},
    "morning_star": {"group": OperatorGroup.CANDLESTICK, "input_dims": [], "output_dim": Dimension.BOOLEAN},
}

def get_operators_by_return_dim(target_dim: Dimension):
    """Backward Chaining: MCTS requests operators that return a specific dimension"""
    ops = []
    for op, meta in OPERATOR_REGISTRY.items():
        # If ANY, it can satisfy anything (assuming children match)
        if meta["output_dim"] == target_dim or meta["output_dim"] == Dimension.ANY:
            ops.append(op)
    return ops
