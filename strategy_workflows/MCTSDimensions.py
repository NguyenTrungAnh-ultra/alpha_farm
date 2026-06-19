# This module defines the dimensional properties of data fields and operators
# to ensure Dimensional Consistency during MCTS alpha generation (as per Alpha2 paper).

from enum import Enum, auto

class Dimension(Enum):
    CURRENCY = auto()   # Prices (open, high, low, close, vwap, etc.)
    VOLUME = auto()     # Volume
    RATIO = auto()      # Dimensionless, percentages, or ratios (RSI, ADX, returns, etc.)
    TIME = auto()       # Time periods, indices
    BOOLEAN = auto()    # True/False signals

# Mapping raw features to dimensions
DATA_FIELD_DIMENSIONS = {
    "pv_open": Dimension.CURRENCY,
    "pv_high": Dimension.CURRENCY,
    "pv_low": Dimension.CURRENCY,
    "pv_close": Dimension.CURRENCY,
    "pv_volume": Dimension.VOLUME,
    "pv_vn30_close": Dimension.CURRENCY,
}

# Mapping indicators to their output dimensions
# Note: Operators that preserve the input dimension (like SMA, MAX, MIN) 
# will be handled dynamically in the MCTS expansion rules.
INDICATOR_DIMENSIONS = {
    # Momentum & Oscillators (Usually return Ratios / Dimensionless)
    "adx": Dimension.RATIO,
    "macd": Dimension.CURRENCY, # MACD is difference of EMAs, so it's currency
    "roc": Dimension.RATIO,
    "rsi": Dimension.RATIO,
    "cmo": Dimension.RATIO,
    "cci": Dimension.RATIO,
    "mfi": Dimension.RATIO,
    "ppo": Dimension.RATIO,
    "rocp": Dimension.RATIO,
    "stoch": Dimension.RATIO,
    "stochrsi": Dimension.RATIO,
    "trix": Dimension.RATIO,
    "ultosc": Dimension.RATIO,
    "willr": Dimension.RATIO,
    "zscore": Dimension.RATIO,
    "price_z": Dimension.RATIO,
    "volume_z": Dimension.RATIO,
    "beta": Dimension.RATIO,
    "correl": Dimension.RATIO,
    
    # Overlap / Moving Averages (Usually preserve input dimension, but let's define default fallback)
    "sma": Dimension.CURRENCY,
    "ema": Dimension.CURRENCY,
    "wma": Dimension.CURRENCY,
    "dema": Dimension.CURRENCY,
    "tema": Dimension.CURRENCY,
    "trima": Dimension.CURRENCY,
    "kama": Dimension.CURRENCY,
    "mama": Dimension.CURRENCY,
    "vwap": Dimension.CURRENCY,
    "rolling_vwap": Dimension.CURRENCY,
    "bbands": Dimension.CURRENCY,
    "sar": Dimension.CURRENCY,
    
    # Volume indicators
    "obv": Dimension.VOLUME,
    "ad": Dimension.VOLUME,
    "adosc": Dimension.VOLUME,
    
    # Volatility indicators
    "atr": Dimension.CURRENCY,
    "natr": Dimension.RATIO,
    "trange": Dimension.CURRENCY,
}

# Mathematical Operator Rules
# Defines what combinations are allowed and what they produce
# e.g., (CURRENCY, CURRENCY) for ADD -> CURRENCY
# e.g., (CURRENCY, CURRENCY) for DIV -> RATIO
# e.g., (CURRENCY, VOLUME) for ADD -> INVALID (None)

def get_add_sub_dimension(dim1, dim2):
    if dim1 == dim2:
        return dim1
    return None # Invalid combination

def get_mul_dimension(dim1, dim2):
    # Just basic rules to avoid explosion. 
    # Usually multiplying a ratio by a value preserves the value's meaning in terms of scaling.
    if dim1 == Dimension.RATIO: return dim2
    if dim2 == Dimension.RATIO: return dim1
    return None

def get_div_dimension(dim1, dim2):
    if dim1 == dim2:
        return Dimension.RATIO
    if dim2 == Dimension.RATIO:
        return dim1
    return None # We can be strict here as per Alpha2 paper
