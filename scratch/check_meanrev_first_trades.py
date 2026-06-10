import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from scratch.run_local_meanrev import MeanRev_CCI_LinearReg

df = load_data('30m', start='2020-01-01', end='2025-01-01')
engine = XNOBacktestEngine()
res = engine.run(MeanRev_CCI_LinearReg(), df)

print(f"Total trades: {res.total_trades}")
print("First 15 completed trades:")
for i, t in enumerate(res.trades[:15]):
    print(f"  Trade {i+1}: Entry Bar {t.entry_bar} ({t.entry_time}) Price {t.entry_price} -> Exit Bar {t.exit_bar} ({t.exit_time}) Price {t.exit_price}")
