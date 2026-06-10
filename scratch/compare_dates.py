import json
import os
import pandas as pd
from datetime import datetime, timezone

sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import sys
sys.path.insert(0, sys_path)
from backtest.engine import load_data

# Load XNO times
with open("scratch/tabs_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

xno_dates = []
for resp in responses:
    if "charts" in resp.get("url", ""):
        data = resp.get("data", {}).get("data", {})
        times = data.get("times", [])
        if len(times) > 100:
            # Parse times to UTC date strings
            xno_dates = [datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%d') for t in times]
            break

print(f"XNO has {len(xno_dates)} dates.")
if xno_dates:
    print(f"XNO first 10: {xno_dates[:10]}")
    print(f"XNO last 10: {xno_dates[-10:]}")

# Load Local times
df = load_data('10m', start='2020-01-01', end='2025-01-01')
local_dates = sorted(df.index.normalize().unique().strftime('%Y-%m-%d').tolist())
print(f"Local has {len(local_dates)} dates.")
print(f"Local first 10: {local_dates[:10]}")
print(f"Local last 10: {local_dates[-10:]}")

# Find differences
xno_set = set(xno_dates)
local_set = set(local_dates)

print(f"\nIn XNO but not Local (first 20): {sorted(list(xno_set - local_set))[:20]}")
print(f"In Local but not XNO (first 20): {sorted(list(local_set - xno_set))[:20]}")
