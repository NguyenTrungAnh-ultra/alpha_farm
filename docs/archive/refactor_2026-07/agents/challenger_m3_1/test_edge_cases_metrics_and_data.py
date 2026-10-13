"""
Additional empirical edge-case testing for data validation and strategy reusability.
"""

import numpy as np
import pandas as pd
import traceback

from core_engine.AlphaEngine import AlphaEngine, AlphaStrategy
from core_engine.AlphaPrimitives import ts_mean, ts_zscore
from core_engine.BacktestEngine import XNOBacktestEngine
from core_engine.CalculateMetrics import compute_metrics


def test_strategy_reusability():
    """Test if running the same strategy instance multiple times causes state leaks."""
    dates1 = pd.date_range("2024-01-01", periods=10, freq="10min")
    df1 = pd.DataFrame({
        "Open": [1000]*10, "High": [1010]*10, "Low": [990]*10, "Close": [1000 + i for i in range(10)], "Volume": [100]*10
    }, index=dates1)

    dates2 = pd.date_range("2024-02-01", periods=15, freq="10min")
    df2 = pd.DataFrame({
        "Open": [2000]*15, "High": [2010]*15, "Low": [1990]*15, "Close": [2000 - i for i in range(15)], "Volume": [200]*15
    }, index=dates2)

    class DynamicStrategy(AlphaStrategy):
        def __algorithm__(self):
            # Long when close > open
            self.set_positions(self.data.close > self.data.open_, 0.2)

    engine = AlphaEngine()
    strat = DynamicStrategy()

    print("--- Test: Strategy Reusability across different DataFrames ---")
    res1 = engine.run(strat, df1)
    len1 = len(res1.positions)
    eq1 = res1.final_equity

    res2 = engine.run(strat, df2)
    len2 = len(res2.positions)
    eq2 = res2.final_equity

    print(f"Run 1 length: {len1}, final equity: {eq1}")
    print(f"Run 2 length: {len2}, final equity: {eq2}")
    
    # Check if internal strategy state (data, _positions) leaked
    if len(strat._positions) != len2:
        print("FAIL: Strategy internal _positions did not update to df2 size!")
    else:
        print("PASS: Strategy internal state reset cleanly on re-execution.")


def test_missing_columns():
    """Test behavior when required OHLC columns are missing."""
    dates = pd.date_range("2024-01-01", periods=10, freq="10min")
    df_missing_close = pd.DataFrame({
        "Open": [1000]*10, "High": [1010]*10, "Low": [990]*10, "Volume": [100]*10
    }, index=dates)

    class SimpleStrat(AlphaStrategy):
        def __algorithm__(self):
            self.set_positions(np.ones(10, dtype=bool), 0.1)

    engine = AlphaEngine()
    print("\n--- Test: Missing 'Close' Column ---")
    try:
        res = engine.run(SimpleStrat(), df_missing_close)
        print("Unexpected PASS, final equity:", res.final_equity)
    except KeyError as e:
        print(f"Expected KeyError caught successfully: missing column {e}")
    except Exception as e:
        print(f"EXCEPTED with {type(e).__name__}: {str(e)}")


def test_duplicate_index():
    """Test behavior with duplicate timestamps in index."""
    dates = pd.to_datetime(["2024-01-01 10:00", "2024-01-01 10:00", "2024-01-01 10:10"])
    df_dup = pd.DataFrame({
        "Open": [1000, 1000, 1010],
        "High": [1005, 1005, 1015],
        "Low": [995, 995, 1005],
        "Close": [1002, 1002, 1012],
        "Volume": [100, 100, 100]
    }, index=dates)

    class SimpleStrat(AlphaStrategy):
        def __algorithm__(self):
            self.set_positions(self.data.close > 1000, 0.2)

    engine = AlphaEngine()
    print("\n--- Test: Duplicate Datetime Index ---")
    try:
        res = engine.run(SimpleStrat(), df_dup)
        metrics = engine.evaluate(SimpleStrat(), df_dup)
        print(f"Run completed. Equity len={len(res.equity_curve)}, final_equity={res.final_equity}")
    except Exception as e:
        print(f"EXCEPTED with {type(e).__name__}: {str(e)}")


def test_custom_indicators_primitive_chaining():
    """Test complex custom strategy chaining multiple primitives."""
    dates = pd.date_range("2024-01-01", periods=100, freq="10min")
    np.random.seed(123)
    close = 1000.0 + np.cumsum(np.random.randn(100))
    df = pd.DataFrame({
        "Open": close, "High": close + 2, "Low": close - 2, "Close": close, "Volume": np.random.randint(50, 200, 100)
    }, index=dates)

    class ComplexAlpha(AlphaStrategy):
        def __algorithm__(self):
            m5 = self.data.close - ts_mean(self.data.close, 5)
            z20 = ts_zscore(self.data.close, 20)
            
            cond_long = (m5 > 0) & (z20 < -0.5)
            cond_short = (m5 < 0) & (z20 > 0.5)
            
            self.set_positions(cond_long, 0.25)
            self.set_positions(cond_short, -0.25)

    engine = AlphaEngine()
    print("\n--- Test: Complex Chained Primitives Strategy ---")
    try:
        res = engine.run(ComplexAlpha(), df)
        metrics = engine.evaluate(ComplexAlpha(), df)
        print(f"ComplexAlpha execution successful. Trades={res.total_trades}, Sharpe={metrics.get('sharpe_ratio'):.4f}, MaxDD={metrics.get('max_drawdown_pct'):.4f}%")
    except Exception as e:
        print(f"EXCEPTED with {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    test_strategy_reusability()
    test_missing_columns()
    test_duplicate_index()
    test_custom_indicators_primitive_chaining()
