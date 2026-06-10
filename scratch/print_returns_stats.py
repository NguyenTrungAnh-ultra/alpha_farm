import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from backtest.runner import SMA_StopAndReverse

df = load_data('10m')
engine = XNOBacktestEngine()
res = engine.run(SMA_StopAndReverse(), df)

equity = res.equity_curve
daily_equity = equity.resample('D').last().dropna()
daily_returns = daily_equity.pct_change().fillna(0.0)

mean = daily_returns.mean()
std = daily_returns.std(ddof=0)
volatility = std * np.sqrt(252)
sharpe = (mean / std) * np.sqrt(252)

print(f"Local resampled daily returns stats:")
print(f"  Mean (avg_return): {mean:.8f}")
print(f"  Std: {std:.8f}")
print(f"  Volatility (annualized): {volatility:.8f}")
print(f"  Sharpe Ratio: {sharpe:.8f}")

print(f"\nXNO Quant stats:")
print(f"  Mean (avg_return): 0.00210425")
print(f"  Volatility: 0.47184693")
print(f"  Sharpe Ratio: 1.40360706")
