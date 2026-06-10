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
        
        # Filter NaNs
        not_nan = self.op.notna(sma)
        long_zone = (close > sma) & not_nan
        short_zone = (~(close > sma)) & not_nan
        
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)

df = load_data('10m', start='2020-01-01', end='2025-01-01')
engine = XNOBacktestEngine()
res = engine.run(SMA_StopAndReverse_WithFilter(), df)

print(f"SMA10 SAR with NaN filter: {res.total_trades} trades")
print(f"First 5 trades:")
for i, t in enumerate(res.trades[:5]):
    print(f"Trade {i+1}: Entry Bar {t.entry_bar} ({t.entry_time}) Price {t.entry_price} -> Exit Bar {t.exit_bar} ({t.exit_time}) Price {t.exit_price}, Contracts {t.contracts}, Fee {t.fee:,.2f}, Net PnL {t.net_pnl:,.2f}")
