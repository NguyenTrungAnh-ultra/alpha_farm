"""
ADX/DI Strategy (talib pre-compute)
====================================
Directional Movement strategy using pre-computed ADX, +DI, -DI via talib.

Rules (mirrors the competition framework logic):
- LONG when ADX > threshold (strong trend) AND +DI > -DI (bullish)
- SHORT when ADX > threshold (strong trend) AND -DI > +DI (bearish)
- FLAT when ADX <= threshold (weak trend) → close any position
"""

import talib
import numpy as np
from backtest.strategy import BaseStrategy
from backtest.engine import Signal


class ADXStrategy(BaseStrategy):
    """
    ADX/DI Directional Movement Strategy.

    Uses talib to pre-compute indicators on the full dataset in setup(),
    then just reads values during the backtest loop.

    Parameters
    ----------
    adx_period : int
        Period for ADX and DI calculation. Default 10.
    adx_threshold : float
        ADX level above which trend is considered strong. Default 30.
    """

    def __init__(self, adx_period: int = 10, adx_threshold: float = 30):
        super().__init__()
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.params = {'adx_period': adx_period, 'adx_threshold': adx_threshold}

        # Pre-computed indicator values (indexed by DataFrame index)
        self._adx = None
        self._plus_di = None
        self._minus_di = None

    def setup(self, data) -> None:
        """Pre-compute ADX, +DI, -DI on the full dataset using talib."""
        high = data['High'].values.astype(np.float64)
        low = data['Low'].values.astype(np.float64)
        close = data['Close'].values.astype(np.float64)

        adx = talib.ADX(high, low, close, timeperiod=self.adx_period)
        plus_di = talib.PLUS_DI(high, low, close, timeperiod=self.adx_period)
        minus_di = talib.MINUS_DI(high, low, close, timeperiod=self.adx_period)

        # Store as dict keyed by DataFrame index for O(1) lookup
        idx = data.index
        self._adx = dict(zip(idx, adx))
        self._plus_di = dict(zip(idx, plus_di))
        self._minus_di = dict(zip(idx, minus_di))

    def on_bar(self, bar) -> None:
        """No-op — indicators are pre-computed in setup()."""
        pass

    def generate_signal(self, bar) -> Signal:
        """
        Generate signal based on ADX strength and DI direction.

        - ADX > threshold AND +DI > -DI → LONG
        - ADX > threshold AND -DI > +DI → SHORT
        - ADX <= threshold → FLAT (close position)
        """
        bar_idx = bar.name  # DataFrame index of this bar
        adx = self._adx.get(bar_idx, np.nan)
        plus_di = self._plus_di.get(bar_idx, np.nan)
        minus_di = self._minus_di.get(bar_idx, np.nan)

        # Not enough data for indicator (NaN during warmup)
        if np.isnan(adx):
            return Signal.FLAT

        strong_trend = adx > self.adx_threshold

        if strong_trend:
            if plus_di > minus_di:
                return Signal.LONG
            elif minus_di > plus_di:
                return Signal.SHORT

        # Weak trend → go flat
        return Signal.FLAT

    def should_exit(self, bar, position) -> bool:
        """
        Exit when:
        - ADX drops below threshold (weak trend)
        - Or direction flips (holding Long but -DI > +DI, or vice versa)
        """
        bar_idx = bar.name
        adx = self._adx.get(bar_idx, np.nan)
        plus_di = self._plus_di.get(bar_idx, np.nan)
        minus_di = self._minus_di.get(bar_idx, np.nan)

        if np.isnan(adx):
            return False

        # Weak trend → exit
        if adx <= self.adx_threshold:
            return True

        # Direction flip
        if position.direction == 1 and minus_di > plus_di:
            return True
        if position.direction == -1 and plus_di > minus_di:
            return True

        return False
