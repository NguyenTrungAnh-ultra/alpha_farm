import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from xno_sdk.engine import SimpleAlgorithm

class SMA_StopAndReverse_WithFilter(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        sma = self.feat.sma(close, timeperiod=10)
        not_nan = self.op.notna(sma)
        long_zone = (close > sma) & not_nan
        short_zone = (~(close > sma)) & not_nan
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)

df = load_data('10m', start='2020-01-03', end='2025-01-01')
engine = XNOBacktestEngine()
res = engine.run(SMA_StopAndReverse_WithFilter(), df)

print(f"SMA10 SAR (Start 2020-01-03) with NaN filter: {res.total_trades} trades")
if res.trades:
    print(f"First trade: {res.trades[0]}")
