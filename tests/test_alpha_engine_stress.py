"""
test_alpha_engine_stress.py
===========================
Empirical stress tests for AlphaEngine & AlphaStrategy (Milestone 3).

Validates:
1. Subclassing AlphaStrategy and custom strategy position generation.
2. AlphaEngine.run() and AlphaEngine.evaluate() on synthetic price data.
3. Edge cases: empty DataFrame, single-row DataFrame, missing columns, zero volume.
"""

import numpy as np
import pandas as pd
import pytest

from core_engine.AlphaEngine import (
    AlphaEngine,
    AlphaStrategy,
    AlphaDataProxy,
    SimpleAlgorithm,
    DataProxy,
)
from core_engine.BacktestEngine import BacktestResult


# ---------------------------------------------------------------------------
# Custom AlphaStrategy Subclasses for Testing
# ---------------------------------------------------------------------------
class CustomTrendStrategy(AlphaStrategy):
    """Subclass testing rolling indicators and dual position masks."""
    def __algorithm__(self):
        sma = self.data.close.rolling(10, min_periods=1).mean()
        long_condition = self.data.close > sma
        short_condition = self.data.close < sma
        self.set_positions(long_condition, 0.4)
        self.set_positions(short_condition, -0.4)


class CustomParametricStrategy(AlphaStrategy):
    """Subclass testing kwargs and volume-price conditions."""
    def __algorithm__(self):
        vol_threshold = self.params.get('vol_threshold', 1000.0)
        target_pos = self.params.get('target_pos', 0.2)
        
        mask = (self.data.volume >= vol_threshold) & (self.data.close >= self.data.open_)
        self.set_positions(mask, target_pos)


class CustomFlatStrategy(AlphaStrategy):
    """Subclass testing zero position generation."""
    def __algorithm__(self):
        pass


# ---------------------------------------------------------------------------
# Fixture for Synthetic Data
# ---------------------------------------------------------------------------
@pytest.fixture
def synthetic_ohlcv_data():
    """Generate synthetic 300-bar OHLCV DataFrame."""
    np.random.seed(123)
    n_bars = 300
    dates = pd.date_range("2024-01-01 09:00", periods=n_bars, freq="15min")
    
    returns = np.random.normal(0.0001, 0.008, size=n_bars)
    close_prices = 1000.0 * np.exp(np.cumsum(returns))
    high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.003, n_bars)))
    low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.003, n_bars)))
    open_prices = close_prices * (1 + np.random.normal(0, 0.001, n_bars))
    volume = np.random.randint(50, 5000, size=n_bars).astype(float)
    
    return pd.DataFrame({
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': volume
    }, index=dates)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_alpha_strategy_subclassing(synthetic_ohlcv_data):
    """Test custom AlphaStrategy subclassing and position generation."""
    strat = CustomTrendStrategy()
    positions = strat.run_algorithm(synthetic_ohlcv_data)
    
    assert isinstance(positions, pd.Series)
    assert len(positions) == len(synthetic_ohlcv_data)
    assert (positions.index == synthetic_ohlcv_data.index).all()
    assert set(positions.unique()).issubset({0.4, -0.4, 0.0})


def test_alpha_strategy_parameters(synthetic_ohlcv_data):
    """Test AlphaStrategy parameter passing and kwargs instantiation."""
    strat = CustomParametricStrategy(vol_threshold=2000.0, target_pos=0.5)
    assert strat.params == {'vol_threshold': 2000.0, 'target_pos': 0.5}
    assert strat.vol_threshold == 2000.0
    assert strat.target_pos == 0.5
    
    positions = strat.run_algorithm(synthetic_ohlcv_data)
    assert isinstance(positions, pd.Series)
    assert set(positions.unique()).issubset({0.5, 0.0})


def test_alpha_engine_run_synthetic(synthetic_ohlcv_data):
    """Test AlphaEngine.run() on synthetic price data."""
    engine = AlphaEngine(initial_capital=1e9)
    strat = CustomTrendStrategy()
    
    result = engine.run(strat, synthetic_ohlcv_data)
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == len(synthetic_ohlcv_data)
    assert result.initial_capital == 1e9
    assert isinstance(result.total_fees, float)
    assert isinstance(result.total_trades, (int, np.integer))


def test_alpha_engine_evaluate_synthetic(synthetic_ohlcv_data):
    """Test AlphaEngine.evaluate() metrics output dictionary."""
    engine = AlphaEngine(initial_capital=1e9)
    strat = CustomTrendStrategy()
    
    metrics = engine.evaluate(strat, synthetic_ohlcv_data)
    assert isinstance(metrics, dict)
    
    expected_keys = [
        'initial_capital', 'net_equity', 'total_profit_pct', 'total_fees_pct',
        'total_trades', 'cagr_pct', 'win_rate_pct', 'profit_factor',
        'sharpe_ratio', 'sortino_ratio', 'max_drawdown_pct', 'volatility',
        'recovery_factor', 'kelly_criterion_pct', 'var_95_pct', 'cvar_95_pct'
    ]
    for key in expected_keys:
        assert key in metrics, f"Missing metric key: {key}"


def test_edge_case_empty_dataframe():
    """Test AlphaEngine.run() and evaluate() on empty DataFrame (0 rows)."""
    engine = AlphaEngine(initial_capital=1e9)
    strat = CustomTrendStrategy()
    empty_df = pd.DataFrame(columns=['Open', 'High', 'Low', 'Close', 'Volume'], index=pd.DatetimeIndex([]))
    
    result = engine.run(strat, empty_df)
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == 0
    assert result.total_trades == 0
    assert result.final_equity == 1e9
    
    metrics = engine.evaluate(strat, empty_df)
    assert isinstance(metrics, dict)
    assert metrics['total_trades'] == 0
    assert metrics['net_equity'] == 1e9


def test_edge_case_single_row_dataframe(synthetic_ohlcv_data):
    """Test AlphaEngine.run() and evaluate() on single-row DataFrame."""
    engine = AlphaEngine(initial_capital=1e9)
    strat = CustomTrendStrategy()
    single_df = synthetic_ohlcv_data.iloc[:1].copy()
    
    result = engine.run(strat, single_df)
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == 1
    assert result.total_trades == 0
    assert result.final_equity == 1e9
    
    metrics = engine.evaluate(strat, single_df)
    assert isinstance(metrics, dict)
    assert metrics['total_trades'] == 0
    assert metrics['net_equity'] == 1e9


def test_edge_case_missing_volume(synthetic_ohlcv_data):
    """Test AlphaDataProxy and AlphaEngine when Volume column is missing."""
    engine = AlphaEngine(initial_capital=1e9)
    strat = CustomTrendStrategy()
    df_no_vol = synthetic_ohlcv_data.drop(columns=['Volume'])
    
    proxy = AlphaDataProxy(df_no_vol)
    assert (proxy.volume == 0.0).all()
    assert len(proxy.volume) == len(df_no_vol)
    
    result = engine.run(strat, df_no_vol)
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == len(synthetic_ohlcv_data)


def test_edge_case_missing_required_price_columns(synthetic_ohlcv_data):
    """Test that missing required price columns (Close, High, Low, Open) raise KeyError."""
    strat = CustomTrendStrategy()
    for col in ['Close', 'High', 'Low', 'Open']:
        df_missing = synthetic_ohlcv_data.drop(columns=[col])
        with pytest.raises(KeyError):
            strat.run_algorithm(df_missing)


def test_edge_case_zero_volume(synthetic_ohlcv_data):
    """Test AlphaEngine execution with all-zero volume series."""
    engine = AlphaEngine(initial_capital=1e9)
    df_zero_vol = synthetic_ohlcv_data.copy()
    df_zero_vol['Volume'] = 0.0
    
    strat_param = CustomParametricStrategy(vol_threshold=100.0, target_pos=0.5)
    positions = strat_param.run_algorithm(df_zero_vol)
    assert (positions == 0.0).all()
    
    strat_trend = CustomTrendStrategy()
    result = engine.run(strat_trend, df_zero_vol)
    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == len(synthetic_ohlcv_data)
    
    metrics = engine.evaluate(strat_trend, df_zero_vol)
    assert isinstance(metrics, dict)
