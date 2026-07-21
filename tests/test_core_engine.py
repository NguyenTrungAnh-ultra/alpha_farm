import pytest
import numpy as np
import pandas as pd
from core_engine.BacktestEngine import AlphaBacktestEngine, BacktestResult
from core_engine.AlphaEngine import (
    AlphaEngine,
    AlphaStrategy,
    AlphaDataProxy,
    SimpleAlgorithm,
    DataProxy,
)
from core_engine.GenerateReport import compute_metrics
from utilities.AppConfig import INITIAL_CAPITAL


class DummyStrategy:
    def __init__(self, positions):
        self.positions = positions

    def run_algorithm(self, df):
        return pd.Series(self.positions, index=df.index)


class SampleAlphaStrategy(AlphaStrategy):
    def __algorithm__(self):
        long_mask = self.data.close > self.data.open_
        self.set_positions(long_mask, 0.2)


def test_alpha_data_proxy(dummy_ohlcv_data):
    proxy = AlphaDataProxy(dummy_ohlcv_data)
    assert proxy.pv_open is dummy_ohlcv_data['Open']
    assert proxy.pv_high is dummy_ohlcv_data['High']
    assert proxy.pv_low is dummy_ohlcv_data['Low']
    assert proxy.pv_close is dummy_ohlcv_data['Close']
    assert len(proxy.pv_volume) == len(dummy_ohlcv_data)
    
    assert proxy.open_ is proxy.pv_open
    assert proxy.high is proxy.pv_high
    assert proxy.low is proxy.pv_low
    assert proxy.close is proxy.pv_close
    assert proxy.volume is proxy.pv_volume
    assert (proxy.index == dummy_ohlcv_data.index).all()
    
    # Test backward compatibility alias
    assert DataProxy is AlphaDataProxy


def test_alpha_strategy(dummy_ohlcv_data):
    strategy = SampleAlphaStrategy(param1=10, param2="test")
    assert strategy.params == {"param1": 10, "param2": "test"}
    assert strategy.param1 == 10
    assert strategy.param2 == "test"
    
    positions = strategy.run_algorithm(dummy_ohlcv_data)
    assert isinstance(positions, pd.Series)
    assert len(positions) == len(dummy_ohlcv_data)
    
    expected_mask = dummy_ohlcv_data['Close'] > dummy_ohlcv_data['Open']
    assert (positions[expected_mask] == 0.2).all()
    assert (positions[~expected_mask] == 0.0).all()
    
    # Test backward compatibility alias
    assert SimpleAlgorithm is AlphaStrategy


def test_alpha_engine_run_and_evaluate(dummy_ohlcv_data):
    engine = AlphaEngine(initial_capital=1e9)
    strategy = SampleAlphaStrategy()
    
    result = engine.run(strategy, dummy_ohlcv_data)
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == len(dummy_ohlcv_data)
    assert result.initial_capital == 1e9
    
    metrics = engine.evaluate(strategy, dummy_ohlcv_data)
    assert isinstance(metrics, dict)
    assert 'cagr_pct' in metrics
    assert 'max_drawdown_pct' in metrics
    assert 'sharpe_ratio' in metrics


def test_pnl_cagr_drawdown(dummy_ohlcv_data):
    engine = AlphaBacktestEngine()
    
    # Simple strategy: go long at bar 10, short at bar 500, flat at 900
    positions = np.zeros(len(dummy_ohlcv_data))
    positions[10:500] = 1.0
    positions[500:900] = -1.0
    
    strategy = DummyStrategy(positions)
    result = engine.run(strategy, dummy_ohlcv_data)
    
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == len(dummy_ohlcv_data)
    assert result.initial_capital == INITIAL_CAPITAL
    
    # test compute_metrics (from GenerateReport)
    metrics = compute_metrics(result)
    assert 'cagr' in metrics
    assert 'max_drawdown_pct' in metrics
    assert 'total_return_pct' in metrics
    
    # Assert they are numbers
    assert isinstance(metrics['cagr'], float)
    assert isinstance(metrics['max_drawdown_pct'], float)


def test_vectorized_margin_call():
    engine = AlphaBacktestEngine()
    
    # Create extreme dummy data where market drops huge, triggering margin call on a long position
    dates = pd.date_range(start='2020-01-01', periods=10, freq='15min')
    # Price dropping extremely fast to trigger margin call
    close_prices = np.array([1000.0, 1000.0, 1000.0, 800.0, 500.0, 400.0, 300.0, 200.0, 100.0, 50.0])
    high_prices = close_prices + 1
    low_prices = close_prices - 1
    open_prices = close_prices
    
    df = pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': np.ones(10) * 1000
    }, index=dates)
    
    # Target positions: constantly long (1.0). Must use .copy() or distinct allocation so engine can mutate it.
    positions = np.ones(10)
    positions = positions.copy()
    strategy = DummyStrategy(positions)
    
    result = engine.run(strategy, df)
    
    # Determine the margin call threshold
    mc_pct = -(engine.margin_rate - engine.maintenance_margin_rate) / engine.margin_rate
    equity_mc_threshold = engine.initial_capital * (1 + mc_pct)
    
    # Check that the equity curve never drops below the margin call threshold
    # Note: we use - 1e-3 tolerance since floating point operations might cause minor variations
    assert (result.equity_curve >= equity_mc_threshold - 1e-3).all(), "Equity dropped below Margin Call threshold"
    
    # Check if we ended exactly at the margin threshold after breach (since market kept dropping)
    assert np.isclose(result.equity_curve.iloc[-1], equity_mc_threshold, rtol=1e-3), "Margin call failed to freeze equity at threshold"
