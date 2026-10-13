"""
Empirical test harness for AlphaEngine and AlphaStrategy.
Runs edge cases and custom strategies to detect failure modes, bugs, or unhandled exceptions.
"""

import traceback
import numpy as np
import pandas as pd
from typing import Dict, Any

from core_engine.AlphaEngine import AlphaEngine, AlphaStrategy, AlphaDataProxy
from core_engine.AlphaPrimitives import ts_mean, ts_zscore, ts_rank, ts_corr
from core_engine.BacktestEngine import BacktestResult


class MACrossoverStrategy(AlphaStrategy):
    """Custom strategy: Short MA / Long MA crossover."""
    def __init__(self, fast_period: int = 5, slow_period: int = 20, pos_size: float = 0.2):
        super().__init__(fast_period=fast_period, slow_period=slow_period, pos_size=pos_size)

    def __algorithm__(self):
        fast_ma = ts_mean(self.data.close, self.fast_period)
        slow_ma = ts_mean(self.data.close, self.slow_period)
        
        long_mask = fast_ma > slow_ma
        short_mask = fast_ma < slow_ma
        
        self.set_positions(long_mask, self.pos_size)
        self.set_positions(short_mask, -self.pos_size)


class MultiPrimitiveStrategy(AlphaStrategy):
    """Custom strategy using zscore, rank, and correlation."""
    def __algorithm__(self):
        z = ts_zscore(self.data.close, 10)
        r = ts_rank(self.data.volume, 10)
        c = ts_corr(self.data.close, self.data.volume, 10)
        
        long_cond = (z < -1.0) & (r > 0.5)
        short_cond = (z > 1.0) & (c < 0.0)
        
        self.set_positions(long_cond, 0.3)
        self.set_positions(short_cond, -0.3)


class ZeroPositionStrategy(AlphaStrategy):
    """Strategy that always keeps 0 position."""
    def __algorithm__(self):
        pass


class ConstantLongStrategy(AlphaStrategy):
    """Strategy that maintains constant long position (+0.5)."""
    def __algorithm__(self):
        self.set_positions(np.ones(len(self.data.index), dtype=bool), 0.5)


class ConstantShortStrategy(AlphaStrategy):
    """Strategy that maintains constant short position (-0.5)."""
    def __algorithm__(self):
        self.set_positions(np.ones(len(self.data.index), dtype=bool), -0.5)


class NaNPositionStrategy(AlphaStrategy):
    """Strategy that produces NaNs in position calculation."""
    def __algorithm__(self):
        # Explicitly assign NaNs to some positions
        pos = pd.Series(np.nan, index=self.data.index)
        self._positions = pos


def create_sample_ohlcv(periods: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=periods, freq="10min")
    np.random.seed(42)
    price_changes = np.random.randn(periods) * 2.0
    close = 1000.0 + np.cumsum(price_changes)
    high = close + np.abs(np.random.randn(periods))
    low = close - np.abs(np.random.randn(periods))
    open_ = close + np.random.randn(periods) * 0.5
    volume = np.random.randint(100, 1000, size=periods).astype(float)
    
    return pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume
    }, index=dates)


def run_empirical_tests() -> Dict[str, Any]:
    engine = AlphaEngine()
    df_normal = create_sample_ohlcv(200)
    results = {}

    # Test 1: MACrossoverStrategy on normal data
    print("--- Test 1: Custom MACrossoverStrategy ---")
    try:
        strat = MACrossoverStrategy(5, 20, 0.2)
        res = engine.run(strat, df_normal)
        metrics = engine.evaluate(strat, df_normal)
        results["test_1_macrossover"] = {
            "status": "PASS",
            "trades": len(res.trades),
            "final_equity": res.final_equity,
            "metrics_keys": list(metrics.keys())
        }
    except Exception as e:
        results["test_1_macrossover"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    # Test 2: MultiPrimitiveStrategy on normal data
    print("--- Test 2: Custom MultiPrimitiveStrategy ---")
    try:
        strat = MultiPrimitiveStrategy()
        res = engine.run(strat, df_normal)
        metrics = engine.evaluate(strat, df_normal)
        results["test_2_multiprimitive"] = {
            "status": "PASS",
            "trades": len(res.trades),
            "final_equity": res.final_equity,
        }
    except Exception as e:
        results["test_2_multiprimitive"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    # Test 3: ZeroPositionStrategy
    print("--- Test 3: ZeroPositionStrategy ---")
    try:
        strat = ZeroPositionStrategy()
        res = engine.run(strat, df_normal)
        metrics = engine.evaluate(strat, df_normal)
        results["test_3_zeropos"] = {
            "status": "PASS",
            "trades": len(res.trades),
            "final_equity": res.final_equity,
            "total_fees": res.total_fees
        }
    except Exception as e:
        results["test_3_zeropos"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    # Test 4: Constant Long & Short Strategies
    print("--- Test 4: Constant Long / Short Strategies ---")
    try:
        strat_long = ConstantLongStrategy()
        res_long = engine.run(strat_long, df_normal)
        metrics_long = engine.evaluate(strat_long, df_normal)
        
        strat_short = ConstantShortStrategy()
        res_short = engine.run(strat_short, df_normal)
        metrics_short = engine.evaluate(strat_short, df_normal)

        results["test_4_constant_long_short"] = {
            "status": "PASS",
            "long_trades": len(res_long.trades),
            "long_final_equity": res_long.final_equity,
            "short_trades": len(res_short.trades),
            "short_final_equity": res_short.final_equity,
        }
    except Exception as e:
        results["test_4_constant_long_short"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    # Test 5: Empty DataFrame
    print("--- Test 5: Empty DataFrame ---")
    try:
        df_empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"], index=pd.DatetimeIndex([]))
        strat = MACrossoverStrategy()
        res = engine.run(strat, df_empty)
        metrics = engine.evaluate(strat, df_empty)
        results["test_5_empty_df"] = {
            "status": "PASS",
            "equity_len": len(res.equity_curve),
            "final_equity": res.final_equity
        }
    except Exception as e:
        results["test_5_empty_df"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    # Test 6: Single-row DataFrame
    print("--- Test 6: Single-row DataFrame ---")
    try:
        df_single = df_normal.iloc[:1]
        strat = ConstantLongStrategy()
        res = engine.run(strat, df_single)
        metrics = engine.evaluate(strat, df_single)
        results["test_6_single_row"] = {
            "status": "PASS",
            "equity_len": len(res.equity_curve),
            "final_equity": res.final_equity,
            "trades": len(res.trades)
        }
    except Exception as e:
        results["test_6_single_row"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    # Test 7: DataFrame with NaNs in OHLCV
    print("--- Test 7: DataFrame with NaNs ---")
    try:
        df_nan = df_normal.copy()
        df_nan.iloc[5:10, df_nan.columns.get_loc("Close")] = np.nan
        df_nan.iloc[15:20, df_nan.columns.get_loc("Volume")] = np.nan
        strat = MACrossoverStrategy()
        res = engine.run(strat, df_nan)
        metrics = engine.evaluate(strat, df_nan)
        results["test_7_nan_dataframe"] = {
            "status": "PASS",
            "final_equity": res.final_equity,
            "trades": len(res.trades)
        }
    except Exception as e:
        results["test_7_nan_dataframe"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    # Test 8: NaN Position Strategy
    print("--- Test 8: NaN Position Strategy ---")
    try:
        strat = NaNPositionStrategy()
        res = engine.run(strat, df_normal)
        metrics = engine.evaluate(strat, df_normal)
        results["test_8_nan_positions"] = {
            "status": "PASS",
            "final_equity": res.final_equity,
            "trades": len(res.trades)
        }
    except Exception as e:
        results["test_8_nan_positions"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    # Test 9: DataFrame missing 'Volume' column
    print("--- Test 9: DataFrame missing Volume column ---")
    try:
        df_no_vol = df_normal.drop(columns=["Volume"])
        proxy = AlphaDataProxy(df_no_vol)
        vol_len = len(proxy.volume)
        vol_sum = proxy.volume.sum()
        results["test_9_no_volume_col"] = {
            "status": "PASS",
            "vol_len": vol_len,
            "vol_sum": vol_sum
        }
    except Exception as e:
        results["test_9_no_volume_col"] = {"status": "FAIL", "error": str(e), "trace": traceback.format_exc()}

    return results


if __name__ == "__main__":
    test_results = run_empirical_tests()
    import json
    print(json.dumps(test_results, indent=2, default=str))
