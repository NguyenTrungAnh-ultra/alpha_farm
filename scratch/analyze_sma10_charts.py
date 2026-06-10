import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone

sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, sys_path)
from backtest.engine import load_data, XNOBacktestEngine
from backtest.runner import SMA_StopAndReverse

# Load XNO charts
with open("scratch/charts_sma10.json", "r", encoding="utf-8") as f:
    charts = json.load(f)

xno_pnls_data = charts["pnls"]["data"]
xno_returns_data = charts["returns"]["data"]

xno_times = xno_pnls_data["times"]
xno_pnls = xno_pnls_data["values"]
xno_returns = xno_returns_data["values"]

xno_dates = [datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%d') for t in xno_times]
print(f"XNO has {len(xno_dates)} daily data points.")

# Load local backtest
df = load_data('10m')
engine = XNOBacktestEngine()
res = engine.run(SMA_StopAndReverse(), df)

equity = res.equity_curve
daily_equity = equity.resample('D').last().dropna()
daily_returns = daily_equity.pct_change().fillna(0.0)
local_dates = daily_equity.index.strftime('%Y-%m-%d').tolist()

# Let's map XNO date -> value (remember XNO dates are shifted by 1 day forward!)
# We shift XNO dates back by 1 day to align with local dates!
shifted_xno_dates = []
for d_str in xno_dates:
    dt = datetime.strptime(d_str, '%Y-%m-%d')
    # Subtract 1 day
    aligned_dt = dt - pd.Timedelta(days=1)
    # If the day falls on weekend (Sat/Sun), pandas Timedelta subtraction might match, but let's check
    # Wait, the easiest way to map is 1-to-1 by index since they both have exactly 1247 dates!
    shifted_xno_dates.append(aligned_dt.strftime('%Y-%m-%d'))

print(f"Shifted XNO dates (index 0 to 5): {shifted_xno_dates[:5]}")
print(f"Local dates (index 0 to 5): {local_dates[:5]}")

# Compare values index by index!
diffs = []
for i in range(len(local_dates)):
    loc_date = local_dates[i]
    xno_date = shifted_xno_dates[i]
    loc_eq = daily_equity.iloc[i]
    xno_pnl = xno_pnls[i]
    
    # XNO equity = 1,000,000,000 + xno_pnl
    xno_eq = 1e9 + xno_pnl
    
    # Difference in equity
    eq_diff = loc_eq - xno_eq
    
    # daily returns
    loc_ret = daily_returns.iloc[i]
    xno_ret = xno_returns[i]
    ret_diff = loc_ret - xno_ret
    
    if abs(eq_diff) > 1.0 or abs(ret_diff) > 1e-6:
        diffs.append({
            "index": i,
            "local_date": loc_date,
            "xno_date_orig": xno_dates[i],
            "local_equity": loc_eq,
            "xno_equity": xno_eq,
            "equity_diff": eq_diff,
            "local_return": loc_ret,
            "xno_return": xno_ret,
            "return_diff": ret_diff
        })

print(f"\nTotal differences: {len(diffs)} / {len(local_dates)}")
if diffs:
    print("\nFirst 10 differences:")
    for d in diffs[:10]:
        print(f"Idx {d['index']:3d}: Local Date {d['local_date']} (XNO {d['xno_date_orig']}) -> Equity Diff: {d['equity_diff']:+,.2f}, Return Diff: {d['return_diff']:+.8f} (Loc {d['local_return']:.8f} vs XNO {d['xno_return']:.8f})")
    
    print("\nLast 10 differences:")
    for d in diffs[-10:]:
        print(f"Idx {d['index']:3d}: Local Date {d['local_date']} (XNO {d['xno_date_orig']}) -> Equity Diff: {d['equity_diff']:+,.2f}, Return Diff: {d['return_diff']:+.8f} (Loc {d['local_return']:.8f} vs XNO {d['xno_return']:.8f})")
