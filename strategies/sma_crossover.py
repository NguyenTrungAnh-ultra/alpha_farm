"""
SMA Crossover Strategy
======================
Simple Moving Average crossover strategy for testing the backtest engine.

Rules:
- LONG when fast SMA crosses above slow SMA
- SHORT when fast SMA crosses below slow SMA
- Exit when opposite signal is generated
"""

from backtest.strategy import BaseStrategy
from backtest.engine import Signal


class SMACrossover(BaseStrategy):
    """
    SMA Crossover Strategy.

    Parameters
    ----------
    fast_period : int
        Period for the fast moving average.
    slow_period : int
        Period for the slow moving average.
    """

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        super().__init__(max_history=slow_period + 5)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.params = {'fast_period': fast_period, 'slow_period': slow_period}

        # Internal state
        self._closes = []
        self._prev_fast_sma = None
        self._prev_slow_sma = None
        self._fast_sma = None
        self._slow_sma = None

    def on_bar(self, bar) -> None:
        """Update SMA values with new close price."""
        self.bars_history.append(bar)
        self._closes.append(bar['Close'])

        # Calculate SMAs
        if len(self._closes) >= self.slow_period:
            self._prev_fast_sma = self._fast_sma
            self._prev_slow_sma = self._slow_sma
            self._fast_sma = sum(self._closes[-self.fast_period:]) / self.fast_period
            self._slow_sma = sum(self._closes[-self.slow_period:]) / self.slow_period

    def generate_signal(self, bar) -> Signal:
        """Generate LONG/SHORT on SMA crossover."""
        # Not enough data yet
        if self._fast_sma is None or self._prev_fast_sma is None:
            return Signal.FLAT

        # Bullish crossover: fast crosses above slow
        if (self._prev_fast_sma <= self._prev_slow_sma and
                self._fast_sma > self._slow_sma):
            return Signal.LONG

        # Bearish crossover: fast crosses below slow
        if (self._prev_fast_sma >= self._prev_slow_sma and
                self._fast_sma < self._slow_sma):
            return Signal.SHORT

        return Signal.FLAT

    def should_exit(self, bar, position) -> bool:
        """Exit when opposite crossover signal occurs."""
        signal = self.generate_signal(bar)
        if position.direction == 1 and signal == Signal.SHORT:
            return True
        if position.direction == -1 and signal == Signal.LONG:
            return True
        return False
