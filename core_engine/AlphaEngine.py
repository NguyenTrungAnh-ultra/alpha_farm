"""
AlphaEngine
===========
High-performance strategy discovery and execution engine facade for alpha_farm.

This module provides:
1. `AlphaDataProxy`: Lightweight data proxy providing strategies access to OHLCV price/volume fields.
2. `AlphaStrategy`: Base class for strategy definition and vectorized signal generation.
3. `AlphaEngine`: Unifying engine facade integrating strategy execution with XNOBacktestEngine
   and performance metrics calculation.
"""

import logging
from typing import Optional, Any
import numpy as np
import pandas as pd

from utilities.AppConfig import (
    INITIAL_CAPITAL,
    MARGIN_RATE,
    MAINTENANCE_MARGIN_RATE,
    FEE_PER_CONTRACT_PER_SIDE,
)
from core_engine.BacktestEngine import AlphaBacktestEngine, BacktestResult, TradeRecord, load_data
from core_engine.CalculateMetrics import compute_metrics

logger = logging.getLogger("core_engine.AlphaEngine")


class AlphaDataProxy:
    """
    Lightweight data proxy providing strategies access to OHLCV data fields.

    Attributes
    ----------
    pv_open : pd.Series
        Open price series.
    pv_high : pd.Series
        High price series.
    pv_low : pd.Series
        Low price series.
    pv_close : pd.Series
        Close price series.
    pv_volume : pd.Series
        Volume series (NaN values filled with 0.0).
    open_ : pd.Series
        Alias for pv_open.
    high : pd.Series
        Alias for pv_high.
    low : pd.Series
        Alias for pv_low.
    close : pd.Series
        Alias for pv_close.
    volume : pd.Series
        Alias for pv_volume.
    index : pd.Index
        Datetime index of the DataFrame.
    """

    def __init__(self, df: pd.DataFrame):
        self._df = df
        self.pv_open = df['Open']
        self.pv_high = df['High']
        self.pv_low = df['Low']
        self.pv_close = df['Close']
        self.pv_volume = df['Volume'].fillna(0.0) if 'Volume' in df.columns else pd.Series(0.0, index=df.index)

    @property
    def open_(self) -> pd.Series:
        return self.pv_open

    @property
    def high(self) -> pd.Series:
        return self.pv_high

    @property
    def low(self) -> pd.Series:
        return self.pv_low

    @property
    def close(self) -> pd.Series:
        return self.pv_close

    @property
    def volume(self) -> pd.Series:
        return self.pv_volume

    @property
    def index(self) -> pd.Index:
        return self._df.index


# Backward compatibility alias
DataProxy = AlphaDataProxy


class AlphaStrategy:
    """
    Base class for strategy definition and execution in AlphaEngine.

    Subclasses override `__algorithm__()` to compute alpha signals and set target positions.
    """

    def __init__(self, **kwargs):
        self.data: Optional[AlphaDataProxy] = None
        self._positions: Optional[pd.Series] = None
        self.params: dict = kwargs.copy()

        for k, v in kwargs.items():
            setattr(self, k, v)

    def _initialize(self, df: pd.DataFrame) -> None:
        """Initialize data proxy and position series for the given DataFrame."""
        self.data = AlphaDataProxy(df)
        self._positions = pd.Series(0.0, index=df.index, dtype=np.float64)

    def set_positions(self, mask: Any, position: float) -> None:
        """
        Set target position size for rows matching the boolean mask.

        Parameters
        ----------
        mask : pd.Series, np.ndarray, or boolean expression
            Boolean mask indicating rows to update.
        position : float
            Target position size (e.g. 0.2 for long, -0.2 for short, 0.0 for flat).
        """
        if hasattr(mask, 'values'):
            bool_mask = mask.fillna(False).astype(bool)
        else:
            bool_mask = np.asarray(mask, dtype=bool)
        self._positions.loc[bool_mask] = position

    def __algorithm__(self) -> None:
        """Subclass must implement strategy logic here."""
        raise NotImplementedError("Subclass must implement __algorithm__()")

    def run_algorithm(self, df: pd.DataFrame) -> pd.Series:
        """
        Execute strategy logic against DataFrame and return target positions series.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV market data.

        Returns
        -------
        pd.Series
            Target position series aligned with df.index.
        """
        self._initialize(df)
        self.__algorithm__()
        return self._positions.copy()


# Backward compatibility alias
SimpleAlgorithm = AlphaStrategy


class AlphaEngine:
    """
    Main engine controller for strategy execution and backtesting in alpha_farm.

    Integrates XNOBacktestEngine for realistic VN30F futures backtest simulation.
    """

    def __init__(
        self,
        initial_capital: float = INITIAL_CAPITAL,
        margin_rate: float = MARGIN_RATE,
        maintenance_margin_rate: float = MAINTENANCE_MARGIN_RATE,
        fee_per_contract: float = FEE_PER_CONTRACT_PER_SIDE,
    ):
        self.initial_capital = initial_capital
        self.margin_rate = margin_rate
        self.maintenance_margin_rate = maintenance_margin_rate
        self.fee_per_contract = fee_per_contract

        self._backtest_engine = AlphaBacktestEngine(
            initial_capital=initial_capital,
            margin_rate=margin_rate,
            maintenance_margin_rate=maintenance_margin_rate,
            fee_per_contract=fee_per_contract,
        )

    def run(self, strategy: AlphaStrategy, df: pd.DataFrame) -> BacktestResult:
        """
        Run backtest simulation for a strategy against market data.

        Parameters
        ----------
        strategy : AlphaStrategy
            Strategy instance.
        df : pd.DataFrame
            OHLCV market data.

        Returns
        -------
        BacktestResult
            Backtest simulation results (equity curve, trades list, fees, metrics inputs).
        """
        return self._backtest_engine.run(strategy, df)

    def evaluate(self, strategy: AlphaStrategy, df: pd.DataFrame) -> dict:
        """
        Run backtest and calculate performance metrics.

        Parameters
        ----------
        strategy : AlphaStrategy
            Strategy instance.
        df : pd.DataFrame
            OHLCV market data.

        Returns
        -------
        dict
            Dictionary of calculated performance and risk metrics (CAGR, Sharpe, Drawdown, etc.).
        """
        result = self.run(strategy, df)
        return compute_metrics(result)
