"""
Stress Test Suite for AlphaEngine & AlphaStrategy
==================================================
Empirical verification script by Challenger M3.1.
Tests custom subclassing, run/evaluate pipeline, and edge cases.
"""

import sys
import os

# Add root directory to python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

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
# 1. Custom AlphaStrategy Subclasses
# ---------------------------------------------------------------------------
class TrendFollowStrategy(AlphaStrategy):
    """Custom strategy: Long when close > 20-period SMA, Short when close < 20-period SMA."""
    def __algorithm__(self):
        close = self.data.close
        sma20 = close.rolling(20, min_periods=1).mean()
        long_mask = close > sma20
        short_mask = close < sma20
        self.set_positions(long_mask, 0.5)
        self.set_positions(short_mask, -0.5)


class VolumeSpikeStrategy(AlphaStrategy):
    """Custom strategy using volume and price change with parameter inputs."""
    def __algorithm__(self):
        threshold = self.params.get('vol_mult', 1.5)
        pos_size = self.params.get('pos_size', 0.3)
        
        vol_mean = self.data.volume.rolling(10, min_periods=1).mean()
        high_vol = self.data.volume > (vol_mean * threshold)
        price_up = self.data.close > self.data.open_
        
        self.set_positions(high_vol & price_up, pos_size)
        self.set_positions(high_vol & (~price_up), -pos_size)


class DummyFlatStrategy(AlphaStrategy):
    """Custom strategy that always stays flat (positions = 0.0)."""
    def __algorithm__(self):
        pass


# ---------------------------------------------------------------------------
# Helper function: Generate Synthetic Data
# ---------------------------------------------------------------------------
def generate_synthetic_ohlcv(n_bars: int = 500, start_price: float = 1000.0, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)
    returns = np.random.normal(0.0002, 0.01, size=n_bars)
    price_path = start_price * np.exp(np.cumsum(returns))
    
    high = price_path * (1 + np.abs(np.random.normal(0, 0.005, n_bars)))
    low = price_path * (1 - np.abs(np.random.normal(0, 0.005, n_bars)))
    open_ = price_path * (1 + np.random.normal(0, 0.002, n_bars))
    close = price_path
    volume = np.random.randint(100, 10000, size=n_bars).astype(float)
    
    dates = pd.date_range(start="2024-01-01 09:00", periods=n_bars, freq="15min")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


# ---------------------------------------------------------------------------
# Test Runner Functions
# ---------------------------------------------------------------------------
def run_all_stress_tests():
    print("==========================================================")
    print("  EMPIRICAL STRESS TEST SUITE FOR ALPHAENGINE & STRATEGY")
    print("==========================================================")
    
    results = {}
    
    # Test 1: Subclassing & Position Generation
    print("\n--- Test 1: AlphaStrategy Subclassing & Position Generation ---")
    df = generate_synthetic_ohlcv(100)
    strat1 = TrendFollowStrategy()
    pos1 = strat1.run_algorithm(df)
    assert isinstance(pos1, pd.Series)
    assert len(pos1) == len(df)
    assert set(pos1.unique()).issubset({0.5, -0.5, 0.0})
    print(f"✓ TrendFollowStrategy generated positions successfully. Value counts:\n{pos1.value_counts()}")
    
    strat2 = VolumeSpikeStrategy(vol_mult=2.0, pos_size=0.4)
    pos2 = strat2.run_algorithm(df)
    assert strat2.vol_mult == 2.0
    assert strat2.pos_size == 0.4
    assert set(pos2.unique()).issubset({0.4, -0.4, 0.0})
    print(f"✓ VolumeSpikeStrategy with params generated positions successfully. Value counts:\n{pos2.value_counts()}")
    
    # Test 2: AlphaEngine.run() and evaluate() on Synthetic Data
    print("\n--- Test 2: AlphaEngine.run() & AlphaEngine.evaluate() ---")
    df_500 = generate_synthetic_ohlcv(500)
    engine = AlphaEngine(initial_capital=1_000_000_000.0)
    
    res = engine.run(strat1, df_500)
    assert isinstance(res, BacktestResult)
    assert len(res.equity_curve) == 500
    assert res.initial_capital == 1_000_000_000.0
    print(f"✓ engine.run() completed. Final equity: {res.final_equity:,.2f}, Total trades: {res.total_trades}, Fees: {res.total_fees:,.2f}")
    
    metrics = engine.evaluate(strat1, df_500)
    assert isinstance(metrics, dict)
    required_keys = ['initial_capital', 'net_equity', 'cagr_pct', 'max_drawdown_pct', 'sharpe_ratio', 'sortino_ratio', 'total_trades']
    for k in required_keys:
        assert k in metrics, f"Missing metric key {k}"
    print(f"✓ engine.evaluate() completed. CAGR: {metrics['cagr_pct']:.2f}%, Sharpe: {metrics['sharpe_ratio']:.2f}, MDD: {metrics['max_drawdown_pct']:.2f}%")
    
    # Test 3: Edge Case - Flat Strategy (No trades)
    print("\n--- Test 3: Edge Case - Flat Strategy (Zero Trades) ---")
    flat_strat = DummyFlatStrategy()
    res_flat = engine.run(flat_strat, df_500)
    assert res_flat.total_trades == 0
    assert res_flat.final_equity == res_flat.initial_capital
    assert len(res_flat.trades) == 0
    metrics_flat = engine.evaluate(flat_strat, df_500)
    assert metrics_flat['total_trades'] == 0
    assert metrics_flat['net_equity'] == 1_000_000_000.0
    print("✓ Flat strategy handled correctly with 0 trades and constant equity.")

    # Test 4: Edge Case - Empty DataFrame (0 rows)
    print("\n--- Test 4: Edge Case - Empty DataFrame (0 rows) ---")
    empty_df = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"], index=pd.DatetimeIndex([]))
    try:
        res_empty = engine.run(strat1, empty_df)
        assert len(res_empty.equity_curve) == 0
        assert res_empty.total_trades == 0
        assert res_empty.final_equity == engine.initial_capital
        print("✓ engine.run() on empty DataFrame executed without crash.")
        
        metrics_empty = engine.evaluate(strat1, empty_df)
        print(f"✓ engine.evaluate() on empty DataFrame completed. Metrics: {metrics_empty}")
    except Exception as e:
        print(f"✗ Exception on Empty DataFrame: {type(e).__name__}: {e}")
        results['empty_df_error'] = str(e)

    # Test 5: Edge Case - Single-Row DataFrame (1 row)
    print("\n--- Test 5: Edge Case - Single-Row DataFrame (1 row) ---")
    single_df = df_500.iloc[:1].copy()
    try:
        res_single = engine.run(strat1, single_df)
        assert len(res_single.equity_curve) == 1
        assert res_single.total_trades == 0
        assert res_single.final_equity == engine.initial_capital
        print("✓ engine.run() on 1-row DataFrame executed without crash.")
        
        metrics_single = engine.evaluate(strat1, single_df)
        assert metrics_single['total_trades'] == 0
        assert metrics_single['net_equity'] == engine.initial_capital
        print(f"✓ engine.evaluate() on 1-row DataFrame completed. Sharpe: {metrics_single['sharpe_ratio']}, MDD: {metrics_single['max_drawdown_pct']}%")
    except Exception as e:
        print(f"✗ Exception on Single-Row DataFrame: {type(e).__name__}: {e}")
        results['single_df_error'] = str(e)

    # Test 6: Edge Case - Missing Columns
    print("\n--- Test 6: Edge Case - Missing Columns ---")
    # Subtest 6a: Missing Volume
    df_no_vol = df_500.drop(columns=["Volume"])
    try:
        proxy_no_vol = AlphaDataProxy(df_no_vol)
        assert (proxy_no_vol.volume == 0.0).all()
        assert len(proxy_no_vol.volume) == len(df_500)
        print("✓ AlphaDataProxy handles missing 'Volume' column by defaulting to 0.0 series.")
        
        res_no_vol = engine.run(strat1, df_no_vol)
        assert len(res_no_vol.equity_curve) == len(df_500)
        print("✓ engine.run() succeeds with missing 'Volume' column.")
    except Exception as e:
        print(f"✗ Exception on Missing Volume: {type(e).__name__}: {e}")
        results['missing_vol_error'] = str(e)
        
    # Subtest 6b: Missing High / Low / Close / Open
    for col in ["Open", "High", "Low", "Close"]:
        df_missing = df_500.drop(columns=[col])
        try:
            strat1.run_algorithm(df_missing)
            print(f"  Warning: Missing {col} did not raise error in strategy.")
        except KeyError as ke:
            print(f"✓ AlphaDataProxy/Strategy raises expected KeyError when required price column '{col}' is missing.")
        except Exception as e:
            print(f"  Unexpected exception type for missing {col}: {type(e).__name__}: {e}")

    # Test 7: Edge Case - Zero Volume
    print("\n--- Test 7: Edge Case - Zero Volume ---")
    df_zero_vol = df_500.copy()
    df_zero_vol["Volume"] = 0.0
    try:
        strat_vol = VolumeSpikeStrategy()
        pos_zero_vol = strat_vol.run_algorithm(df_zero_vol)
        assert (pos_zero_vol == 0.0).all()
        print("✓ VolumeSpikeStrategy correctly generates 0 positions when Volume is 0.")
        
        res_zero_vol = engine.run(strat1, df_zero_vol)
        assert len(res_zero_vol.equity_curve) == len(df_500)
        metrics_zero_vol = engine.evaluate(strat1, df_zero_vol)
        print("✓ engine.run() and engine.evaluate() complete successfully on DataFrame with Zero Volume.")
    except Exception as e:
        print(f"✗ Exception on Zero Volume: {type(e).__name__}: {e}")
        results['zero_vol_error'] = str(e)

    print("\n==========================================================")
    print("  STRESS TEST COMPLETED")
    print("==========================================================")
    return results

if __name__ == "__main__":
    run_all_stress_tests()
