"""
Baselines
=========
The two reference strategies of the walk-forward comparison, as target-position series for `AlphaBacktestEngine`
(contract count fixed from the initial capital, a signal at bar t fills at t + 1, same fees and margin as every other
configuration). Both trade at the position size of the discovered strategies (`_TemplateStrategy.position_scale`),
so exposure is comparable.

    buy and hold   always long
    TSMOM          time-series momentum (Moskowitz, Ooi and Pedersen 2012) on bars: long when the return over the
                   past L bars is positive, short when negative, flat when zero or unknown. No volatility scaling:
                   the engine fixes the contract count. L is one of the pre-registered lookbacks of 1 trading day,
                   1 week and 1 month, converted to bars with the median number of bars per session of the segment
                   the choice is made from.
"""

from typing import Dict

import numpy as np
import pandas as pd

from strategy_workflows.MCTSEngine import _TemplateStrategy

POSITION_SCALE = _TemplateStrategy.position_scale
# Pre-registered lookbacks in trading sessions: a day, a week of 5 sessions, a month of 21 (252 / 12).
TSMOM_LOOKBACK_SESSIONS: Dict[str, int] = {'day': 1, 'week': 5, 'month': 21}


def buy_hold_positions(index: pd.Index) -> pd.Series:
    """Always long at the discovered strategies' position size."""
    return pd.Series(POSITION_SCALE, index=index, dtype=np.float64)


def bars_per_session(frame: pd.DataFrame) -> int:
    """Median number of bars per calendar day that has bars."""
    counts = pd.Series(1, index=frame.index).groupby(frame.index.normalize()).sum()
    if counts.empty:
        raise ValueError("No bars to count sessions in")
    return int(round(float(counts.median())))


def tsmom_lookbacks(sessions_bars: int) -> Dict[str, int]:
    """Lookback label -> number of bars, from the bars per session."""
    return {label: sessions * sessions_bars for label, sessions in TSMOM_LOOKBACK_SESSIONS.items()}


def tsmom_positions(close: pd.Series, lookback_bars: int) -> pd.Series:
    """sign(close_t / close_{t-L} - 1) at the position size; 0 where the return is zero or not yet defined."""
    if lookback_bars < 1:
        raise ValueError(f"lookback must be at least 1 bar, got {lookback_bars}")
    past_return = close / close.shift(lookback_bars) - 1.0
    return POSITION_SCALE * np.sign(past_return).fillna(0.0)
