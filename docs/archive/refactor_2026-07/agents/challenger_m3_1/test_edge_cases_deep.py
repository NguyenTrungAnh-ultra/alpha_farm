"""
Deep edge-case stress test for AlphaEngine, BacktestEngine, and CalculateMetrics.
"""

import numpy as np
import pandas as pd
import traceback
from typing import Dict, Any

from core_engine.AlphaEngine import AlphaEngine, AlphaStrategy, AlphaDataProxy
from core_engine.BacktestEngine import XNOBacktestEngine, BacktestResult
from core_engine.CalculateMetrics import compute_metrics


def test_nan_prices():
    """Test behavior when prices contain NaN, Inf, zero, or negative numbers."""
    dates = pd.date_range("2024-01-01", periods=10, freq="10min")
    df_nan_price = pd.DataFrame({
        "Open": [1000, 1005, np.nan, 1010, 1015, 1020, 1025, 1030, 1035, 1040],
        "High": [1005, 1010, 1015, 1020, 1025, 1030, 1035, 1040, 1045, 1050],
        "Low": [995, 1000, 1005, 1005, 1010, 1015, 1020, 1025, 1030, 1035],
        "Close": [1000, 1005, np.nan, 1010, 1015, 1020, 1025, 1030, 1035, 1040],
        "Volume": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
    }, index=dates)

    class FixedLongStrat(AlphaStrategy):
        def __algorithm__(self):
            self.set_positions(np.ones(len(self.data.index), dtype=bool), 0.2)

    engine = AlphaEngine()
    try:
        res = engine.run(FixedLongStrat(), df_nan_price)
        metrics = engine.evaluate(FixedLongStrat(), df_nan_price)
        print("NAN Price test result:")
        print("  Equity curve contains NaN count:", res.equity_curve.isna().sum())
        print("  Final equity:", res.final_equity)
        print("  CAGR pct in metrics:", metrics.get("cagr_pct"))
        print("  Sharpe ratio in metrics:", metrics.get("sharpe_ratio"))
        print("  Max drawdown in metrics:", metrics.get("max_drawdown_pct"))
    except Exception as e:
        print("NAN Price test raised EXCEPTION:", type(e).__name__, str(e))
        traceback.print_exc()


def test_invalid_position_values():
    """Test behavior when strategy produces NaN, Inf, -Inf, or extreme positions like 1e6."""
    dates = pd.date_range("2024-01-01", periods=10, freq="10min")
    df = pd.DataFrame({
        "Open": [1000]*10,
        "High": [1010]*10,
        "Low": [990]*10,
        "Close": [1000]*10,
        "Volume": [100]*10
    }, index=dates)

    class BadPosStrat(AlphaStrategy):
        def __init__(self, val):
            super().__init__()
            self.val = val
        def __algorithm__(self):
            self._positions = pd.Series(self.val, index=self.data.index)

    engine = AlphaEngine()
    for label, val in [("NaN", np.nan), ("Inf", np.inf), ("-Inf", -np.inf), ("Extreme 1e6", 1e6)]:
        try:
            print(f"\n--- Testing Invalid Position Value: {label} ---")
            res = engine.run(BadPosStrat(val), df)
            metrics = engine.evaluate(BadPosStrat(val), df)
            print(f"  Final equity: {res.final_equity}, Total trades: {res.total_trades}")
        except Exception as e:
            print(f"  EXCEPTED with {type(e).__name__}: {str(e)}")


def test_short_dataframes():
    """Test 0-row, 1-row, 2-row dataframes with active signals."""
    class AlwaysActiveStrat(AlphaStrategy):
        def __algorithm__(self):
            self.set_positions(np.ones(len(self.data.index), dtype=bool), 0.5)

    engine = AlphaEngine()

    for n in [0, 1, 2, 3]:
        print(f"\n--- Testing DataFrame with {n} rows ---")
        dates = pd.date_range("2024-01-01", periods=n, freq="10min")
        df = pd.DataFrame({
            "Open": [1000.0]*n,
            "High": [1010.0]*n,
            "Low": [990.0]*n,
            "Close": [1005.0 + i for i in range(n)],
            "Volume": [100.0]*n
        }, index=dates)

        try:
            res = engine.run(AlwaysActiveStrat(), df)
            metrics = engine.evaluate(AlwaysActiveStrat(), df)
            print(f"  {n}-row run OK. Equity len={len(res.equity_curve)}, trades={res.total_trades}, final_eq={res.final_equity}")
        except Exception as e:
            print(f"  {n}-row EXCEPTED with {type(e).__name__}: {str(e)}")
            traceback.print_exc()


def test_zero_variance_equity():
    """Test metrics calculation when equity is completely flat (e.g. constant initial capital)."""
    dates = pd.date_range("2024-01-01", periods=50, freq="10min")
    df = pd.DataFrame({
        "Open": [1000]*50, "High": [1005]*50, "Low": [995]*50, "Close": [1000]*50, "Volume": [100]*50
    }, index=dates)

    class ZeroStrat(AlphaStrategy):
        def __algorithm__(self):
            pass

    engine = AlphaEngine()
    print("\n--- Testing Zero Variance Equity ---")
    try:
        metrics = engine.evaluate(ZeroStrat(), df)
        print("  Sharpe:", metrics.get("sharpe_ratio"))
        print("  Sortino:", metrics.get("sortino_ratio"))
        print("  Calmar:", metrics.get("calmar_ratio"))
        print("  Max DD:", metrics.get("max_drawdown_pct"))
        print("  Volatility:", metrics.get("volatility"))
    except Exception as e:
        print("  EXCEPTED with", type(e).__name__, str(e))


if __name__ == "__main__":
    test_nan_prices()
    test_invalid_position_values()
    test_short_dataframes()
    test_zero_variance_equity()
