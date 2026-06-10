import numpy as np
import pandas as pd
import os

sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, sys_path)
from backtest.engine import load_data

df = load_data('10m', start='2020-01-01', end='2022-12-31')
dates = sorted(df.index.normalize().unique().strftime('%Y-%m-%d').tolist())
N = len(dates)
print(f"Number of dates in Train stage: {N}")

val = -0.005679999999999762
returns = np.zeros(N)
returns[3] = val  # The day of the trade

mean = np.mean(returns)
std = np.std(returns, ddof=0)
sharpe = (mean / std) * np.sqrt(252)
print(f"Calculated Train Sharpe (population std, N={N}): {sharpe:.16f}")
print(f"XNO Quant Train Sharpe: -0.5796550670490436")
