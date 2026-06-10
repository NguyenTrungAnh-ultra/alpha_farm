import json
import os
from datetime import datetime, timezone

path = "scratch/tabs_captured_responses.json"
if not os.path.exists(path):
    path = "scratch/probe_captured_responses.json"

with open(path, "r", encoding="utf-8") as f:
    responses = json.load(f)

for resp in responses:
    url = resp.get("url", "")
    if "charts" in url:
        data = resp.get("data", {}).get("data", {})
        times = data.get("times", [])
        if len(times) > 100:
            # Parse dates
            dates = [datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%d') for t in times]
            
            # Count dates <= '2023-01-01' (since end date is 2022-12-31)
            train_dates = [d for d in dates if d <= '2023-01-01']
            print(f"Total dates in chart: {len(dates)}")
            print(f"Train dates (<= 2023-01-01): {len(train_dates)}")
            if train_dates:
                print(f"First train date: {train_dates[0]}, Last train date: {train_dates[-1]}")
            break
