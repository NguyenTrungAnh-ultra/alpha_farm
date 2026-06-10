import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from backtest.metrics import compute_metrics
from scratch.run_local_meanrev import MeanRev_CCI_LinearReg

# 1. Run local backtest
df = load_data('30m', start='2020-01-01', end='2025-01-01')
engine = XNOBacktestEngine()
res = engine.run(MeanRev_CCI_LinearReg(), df)

# 2. Get local equity curve resampled to daily close
equity = res.equity_curve
daily_equity = equity.resample('D').last().dropna()

initial = res.initial_capital

# 3. Calculate daily returns using constant capital
daily_pnl_change = daily_equity.diff().fillna(0.0)
daily_returns_const = daily_pnl_change / initial

# Calculate daily returns using rolling equity (pct_change)
daily_returns_rolling = daily_equity.pct_change().fillna(0.0)

# 4. Compare performance metrics
web = {
    "sharpe": 1.6322330739513347,
    "sortino": 2.847983627228581,
    "volatility": 0.1350891804215193,
    "max_drawdown": -0.11883396166303817,
    "omega": 1.6040962186105094,
    "var": -0.013157403481526286,
    "cvar": -0.017531716021658143,
    "ulcer_index": 0.029512098883525094,
    "recovery_factor": 14.518408507473875
}

def calc_all(returns, daily_eq, label):
    # Sharpe
    mean = returns.mean()
    std_p = returns.std(ddof=0)
    sharpe = mean / std_p * np.sqrt(252) if std_p > 0 else 0
    
    # Sortino
    downside = returns[returns < 0]
    downside_std = downside.std(ddof=0) if len(downside) > 0 else 0
    sortino = mean / downside_std * np.sqrt(252) if downside_std > 0 else 0
    
    # Volatility
    volatility = std_p * np.sqrt(252)
    
    # Drawdown & Max DD
    rolling_max = daily_eq.cummax()
    drawdown = (daily_eq - rolling_max) / rolling_max
    max_dd = drawdown.min()
    
    # Omega
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    omega = gains / losses if losses > 0 else 0
    
    # VaR
    var_95 = mean - 1.6448536269514722 * std_p
    
    # CVaR (historical ES on daily returns)
    hist_var_threshold = np.percentile(returns, 5)
    cvar = returns[returns <= hist_var_threshold].mean()
    
    # Ulcer Index
    ulcer = np.sqrt((drawdown ** 2).mean())
    
    # Recovery Factor
    recovery = (daily_eq.iloc[-1] - initial) / (abs(max_dd) * initial) if max_dd != 0 else 0
    
    print(f"\n--- Metrics with {label} ---")
    print(f"  Sharpe:      {sharpe:.8f} (Web: {web['sharpe']:.8f}) Match: {abs(sharpe - web['sharpe']) < 1e-4}")
    print(f"  Sortino:     {sortino:.8f} (Web: {web['sortino']:.8f}) Match: {abs(sortino - web['sortino']) < 1e-4}")
    print(f"  Volatility:  {volatility:.8f} (Web: {web['volatility']:.8f}) Match: {abs(volatility - web['volatility']) < 1e-4}")
    print(f"  Max DD:      {max_dd*100:.6f}% (Web: {web['max_drawdown']*100:.6f}%)")
    print(f"  Omega:       {omega:.8f} (Web: {web['omega']:.8f}) Match: {abs(omega - web['omega']) < 1e-4}")
    print(f"  VaR (95%):   {var_95*100:.6f}% (Web: {web['var']*100:.6f}%)")
    print(f"  CVaR (95%):  {cvar*100:.6f}% (Web: {web['cvar']*100:.6f}%)")
    print(f"  Ulcer Index: {ulcer:.8f} (Web: {web['ulcer_index']:.8f}) Match: {abs(ulcer - web['ulcer_index']) < 1e-4}")
    print(f"  Recovery:    {recovery:.8f} (Web: {web['recovery_factor']:.8f}) Match: {abs(recovery - web['recovery_factor']) < 1e-2}")

calc_all(daily_returns_const, daily_equity, "Constant Capital Returns")
calc_all(daily_returns_rolling, daily_equity, "Rolling Equity Returns")
