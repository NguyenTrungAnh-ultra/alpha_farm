import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from backtest.runner import STRATEGIES
from backtest.metrics import compute_metrics

engine = XNOBacktestEngine()
df = load_data('10m', start='2020-01-03', end='2022-12-31')

print("SMA verification strategies run on Train period (2020-01-03 to 2022-12-31):")
for name in ['sma10_sar', 'sma10_lf', 'sma_channel', 'sma5_20', 'sma3_1000']:
    StrategyClass = STRATEGIES[name]
    res = engine.run(StrategyClass(), df)
    m = compute_metrics(res)
    print(f"\n{name}:")
    print(f"  Total Trades: {m['total_trades']}")
    print(f"  Total Fees %: {m['total_fees_pct']:.2f}%")
    print(f"  Cumulative Return: {m['cumulative_return_pct']:.2f}%")
    print(f"  Net Equity: {m['net_equity']:,.0f}")
