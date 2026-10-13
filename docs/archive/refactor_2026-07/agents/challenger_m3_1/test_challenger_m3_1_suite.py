"""
Formal empirical test suite for Challenger 1 M3: AlphaEngine & AlphaStrategy execution.
"""

import pytest
import numpy as np
import pandas as pd

from core_engine.AlphaEngine import AlphaEngine, AlphaStrategy, AlphaDataProxy
from core_engine.AlphaPrimitives import ts_mean, ts_zscore, ts_rank, ts_corr
from core_engine.BacktestEngine import BacktestResult


class MACrossoverStrategy(AlphaStrategy):
    """Moving average crossover strategy using ts_mean primitive."""
    def __init__(self, fast_period: int = 5, slow_period: int = 20, pos_size: float = 0.2):
        super().__init__(fast_period=fast_period, slow_period=slow_period, pos_size=pos_size)

    def __algorithm__(self):
        fast_ma = ts_mean(self.data.close, self.fast_period)
        slow_ma = ts_mean(self.data.close, self.slow_period)
        
        self.set_positions(fast_ma > slow_ma, self.pos_size)
        self.set_positions(fast_ma < slow_ma, -self.pos_size)


class MultiPrimitiveStrategy(AlphaStrategy):
    """Strategy using ts_zscore, ts_rank, and ts_corr primitives."""
    def __algorithm__(self):
        z = ts_zscore(self.data.close, 10)
        r = ts_rank(self.data.volume, 10)
        c = ts_corr(self.data.close, self.data.volume, 10)
        
        self.set_positions((z < -1.0) & (r > 0.5), 0.3)
        self.set_positions((z > 1.0) & (c < 0.0), -0.3)


class ZeroPositionStrategy(AlphaStrategy):
    """Strategy maintaining constant zero position."""
    def __algorithm__(self):
        pass


class ConstantLongStrategy(AlphaStrategy):
    """Strategy maintaining constant long position (+0.5)."""
    def __algorithm__(self):
        self.set_positions(np.ones(len(self.data.index), dtype=bool), 0.5)


class ConstantShortStrategy(AlphaStrategy):
    """Strategy maintaining constant short position (-0.5)."""
    def __algorithm__(self):
        self.set_positions(np.ones(len(self.data.index), dtype=bool), -0.5)


@pytest.fixture
def sample_ohlcv_data():
    dates = pd.date_range("2024-01-01", periods=100, freq="10min")
    np.random.seed(42)
    price_changes = np.random.randn(100) * 2.0
    close = 1000.0 + np.cumsum(price_changes)
    high = close + np.abs(np.random.randn(100))
    low = close - np.abs(np.random.randn(100))
    open_ = close + np.random.randn(100) * 0.5
    volume = np.random.randint(100, 1000, size=100).astype(float)
    
    return pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume
    }, index=dates)


def test_custom_alpha_strategy_macrossover(sample_ohlcv_data):
    engine = AlphaEngine()
    strat = MACrossoverStrategy(5, 20, 0.2)
    
    res = engine.run(strat, sample_ohlcv_data)
    metrics = engine.evaluate(strat, sample_ohlcv_data)
    
    assert isinstance(res, BacktestResult)
    assert len(res.equity_curve) == len(sample_ohlcv_data)
    assert res.initial_capital == 1e9
    assert isinstance(metrics, dict)
    assert "sharpe_ratio" in metrics
    assert "max_drawdown_pct" in metrics


def test_custom_alpha_strategy_multi_primitive(sample_ohlcv_data):
    engine = AlphaEngine()
    strat = MultiPrimitiveStrategy()
    
    res = engine.run(strat, sample_ohlcv_data)
    metrics = engine.evaluate(strat, sample_ohlcv_data)
    
    assert isinstance(res, BacktestResult)
    assert len(res.equity_curve) == len(sample_ohlcv_data)
    assert "cagr_pct" in metrics


def test_edge_case_empty_dataframe():
    engine = AlphaEngine()
    df_empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"], index=pd.DatetimeIndex([]))
    strat = MACrossoverStrategy()
    
    res = engine.run(strat, df_empty)
    metrics = engine.evaluate(strat, df_empty)
    
    assert len(res.equity_curve) == 0
    assert res.final_equity == 1e9
    assert res.total_trades == 0
    assert res.total_fees == 0.0


def test_edge_case_single_and_two_row_dataframe(sample_ohlcv_data):
    engine = AlphaEngine()
    strat = ConstantLongStrategy()
    
    # Single row
    df_1 = sample_ohlcv_data.iloc[:1]
    res_1 = engine.run(strat, df_1)
    assert len(res_1.equity_curve) == 1
    assert res_1.total_trades == 0  # Shift(1) eliminates trade execution on bar 0
    
    # Two rows
    df_2 = sample_ohlcv_data.iloc[:2]
    res_2 = engine.run(strat, df_2)
    assert len(res_2.equity_curve) == 2
    assert res_2.total_trades == 1  # Trade executes on bar 1


def test_edge_case_zero_position_strategy(sample_ohlcv_data):
    engine = AlphaEngine()
    strat = ZeroPositionStrategy()
    
    res = engine.run(strat, sample_ohlcv_data)
    metrics = engine.evaluate(strat, sample_ohlcv_data)
    
    assert res.total_trades == 0
    assert res.total_fees == 0.0
    assert res.final_equity == 1e9
    assert metrics["max_drawdown_pct"] == 0.0


def test_edge_case_constant_long_short_strategies(sample_ohlcv_data):
    engine = AlphaEngine()
    
    strat_long = ConstantLongStrategy()
    res_long = engine.run(strat_long, sample_ohlcv_data)
    
    strat_short = ConstantShortStrategy()
    res_short = engine.run(strat_short, sample_ohlcv_data)
    
    assert isinstance(res_long, BacktestResult)
    assert isinstance(res_short, BacktestResult)
    assert res_long.initial_capital == 1e9
    assert res_short.initial_capital == 1e9


def test_edge_case_nan_prices_and_positions(sample_ohlcv_data):
    engine = AlphaEngine()
    df_nan = sample_ohlcv_data.copy()
    df_nan.iloc[10:15, df_nan.columns.get_loc("Close")] = np.nan
    
    strat = MACrossoverStrategy()
    res = engine.run(strat, df_nan)
    metrics = engine.evaluate(strat, df_nan)
    
    # Empirical observation: NaN in close price propagates NaNs into equity_curve
    assert res.equity_curve.isna().sum() > 0
    assert np.isnan(res.final_equity)


def test_edge_case_inf_position_handling(sample_ohlcv_data):
    engine = AlphaEngine()
    
    class InfStrat(AlphaStrategy):
        def __algorithm__(self):
            self._positions = pd.Series(np.inf, index=self.data.index)
            
    strat = InfStrat()
    # Expect OverflowError when converting np.inf position to contracts count in calc_contracts
    with pytest.raises(OverflowError):
        engine.run(strat, sample_ohlcv_data)


def test_edge_case_missing_volume_column(sample_ohlcv_data):
    df_no_vol = sample_ohlcv_data.drop(columns=["Volume"])
    proxy = AlphaDataProxy(df_no_vol)
    
    assert proxy.volume is not None
    assert len(proxy.volume) == len(sample_ohlcv_data)
    assert (proxy.volume == 0.0).all()


def test_strategy_reusability(sample_ohlcv_data):
    engine = AlphaEngine()
    strat = MACrossoverStrategy()
    
    df1 = sample_ohlcv_data.iloc[:30]
    df2 = sample_ohlcv_data.iloc[:60]
    
    res1 = engine.run(strat, df1)
    res2 = engine.run(strat, df2)
    
    assert len(res1.positions) == 30
    assert len(res2.positions) == 60
