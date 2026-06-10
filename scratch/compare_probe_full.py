import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone

sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, sys_path)
from backtest.engine import load_data, XNOBacktestEngine
from xno_sdk.engine import SimpleAlgorithm

class Probe(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        is_first_bar = self.op.isna(self.op.shift(close, 1))
        index_series = self.op.bars_since(is_first_bar)
        mask = (index_series >= 100) & (index_series <= 105)
        self.set_positions(mask, position=1.0)

# Load XNO charts for c0RX7j3DAz (Probe)
with open("scratch/tabs_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

xno_pnls = []
xno_returns = []
xno_times = []

for resp in responses:
    url = resp.get("url", "")
    if "c0RX7j3DAz/charts?series=pnls" in url:
        xno_pnls = resp.get("data", {}).get("data", {}).get("values", [])
        xno_times = resp.get("data", {}).get("data", {}).get("times", [])
    elif "c0RX7j3DAz/charts?series=returns" in url:
        xno_returns = resp.get("data", {}).get("data", {}).get("values", [])

print(f"XNO PnLs length: {len(xno_pnls)}")
print(f"XNO Returns length: {len(xno_returns)}")

# Local backtest
df = load_data('10m', start='2020-01-01', end='2022-12-31')
engine = XNOBacktestEngine()
res = engine.run(Probe(), df)

equity = res.equity_curve
daily_equity = equity.resample('D').last().dropna()
daily_returns = daily_equity.pct_change().fillna(0.0)

print(f"Local daily equity length: {len(daily_equity)}")

# Check index-by-index match
matches_pnl = 0
matches_ret = 0

for i in range(min(len(xno_pnls), len(daily_equity))):
    local_pnl = daily_equity.iloc[i] - 1e9
    x_pnl = xno_pnls[i]
    local_ret = daily_returns.iloc[i]
    x_ret = xno_returns[i]
    
    if abs(local_pnl - x_pnl) < 1.0:
        matches_pnl += 1
    if abs(local_ret - x_ret) < 1e-7:
        matches_ret += 1
    else:
        # print first few mismatches if any
        if matches_ret < 5:
            print(f"Mismatch at index {i}: Local PnL {local_pnl:,.2f} (XNO {x_pnl:,.2f}), Local Ret {local_ret:.8f} (XNO {x_ret:.8f})")

print(f"PnL Matches: {matches_pnl} / {min(len(xno_pnls), len(daily_equity))}")
print(f"Return Matches: {matches_ret} / {min(len(xno_returns), len(daily_returns))}")
