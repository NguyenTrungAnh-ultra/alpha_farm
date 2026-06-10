import sys
import os
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from scratch.run_local_meanrev import MeanRev_CCI_LinearReg

# 1. Load web PnLs
with open("scratch/probe_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

web_pnls = []
for resp in responses:
    if "KHsBRRvjYL/charts?series=pnls" in resp.get("url", ""):
        web_pnls = resp.get("data", {}).get("data", {}).get("values", [])
        break

if not web_pnls:
    print("Web PnLs not found in captured responses.")
    sys.exit(1)

print(f"Web PnLs length: {len(web_pnls)}")

# 2. Run local backtest
df = load_data('30m', start='2020-01-01', end='2025-01-01')
engine = XNOBacktestEngine()
res = engine.run(MeanRev_CCI_LinearReg(), df)

local_equity = res.equity_curve
local_daily_equity = local_equity.resample('D').last().dropna()
local_pnls = (local_daily_equity - 1e9).tolist()

print(f"Local PnLs length: {len(local_pnls)}")

# Note: XNO dates are shifted +1 day, but the count is exactly 1247.
# Let's compare index-by-index.
divergence_idx = -1
for i in range(min(len(web_pnls), len(local_pnls))):
    diff = abs(web_pnls[i] - local_pnls[i])
    if diff > 1.0:
        divergence_idx = i
        break

if divergence_idx == -1:
    print("No divergence found! All daily PnLs match exactly!")
else:
    print(f"\nDivergence found at index {divergence_idx}:")
    # Let's get the local date corresponding to this index
    local_date = local_daily_equity.index[divergence_idx].strftime('%Y-%m-%d')
    print(f"  Local Date: {local_date}")
    print(f"  Web PnL:   {web_pnls[divergence_idx]:,.2f}")
    print(f"  Local PnL: {local_pnls[divergence_idx]:,.2f}")
    print(f"  Difference: {web_pnls[divergence_idx] - local_pnls[divergence_idx]:,.2f}")
    
    # Print the last few matches before divergence
    print("\n--- Last 5 matching days ---")
    start_idx = max(0, divergence_idx - 5)
    for idx in range(start_idx, divergence_idx):
        ld = local_daily_equity.index[idx].strftime('%Y-%m-%d')
        print(f"  Index {idx} ({ld}): Web={web_pnls[idx]:,.2f}, Local={local_pnls[idx]:,.2f}")
        
    # Let's inspect trades around this date
    print("\n--- Local trades around this date ---")
    div_date_start = local_daily_equity.index[max(0, divergence_idx - 2)]
    div_date_end = local_daily_equity.index[min(len(local_daily_equity)-1, divergence_idx + 5)]
    
    for t in res.trades:
        if t.entry_time >= div_date_start and t.entry_time <= div_date_end:
            print(f"  Local Trade: Entry={t.entry_time} Price={t.entry_price} -> Exit={t.exit_time} Price={t.exit_price} PnL={t.net_pnl:,.2f}")
