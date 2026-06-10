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

# 5% percentile VaR
var_95 = np.percentile(daily_returns, 5)
# CVaR (Expected Shortfall)
cvar_95 = daily_returns[daily_returns <= var_95].mean()

print(f"Daily returns length: {len(daily_returns)}")
print(f"Calculated VaR 95: {var_95 * 100:.6f}%")
print(f"XNO Quant VaR 95: -4.678835%")
print(f"Calculated CVaR 95: {cvar_95 * 100:.6f}%")
print(f"XNO Quant CVaR 95: -7.029623%")
