import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from backtest.runner import SMA_StopAndReverse

engine = XNOBacktestEngine()

print("SMA10 Stop & Reverse Trade Counts:")

# 1. Starting 2020-01-01 (loads 2020-01-02)
df1 = load_data('10m', start='2020-01-01', end='2025-01-01')
res1 = engine.run(SMA_StopAndReverse(), df1)
print(f"Start 2020-01-01: {res1.total_trades} trades, first trade: {res1.trades[0].entry_time if res1.trades else 'None'}")

# 2. Starting 2020-01-03
df2 = load_data('10m', start='2020-01-03', end='2025-01-01')
res2 = engine.run(SMA_StopAndReverse(), df2)
print(f"Start 2020-01-03: {res2.total_trades} trades, first trade: {res2.trades[0].entry_time if res2.trades else 'None'}")
