import json
import os
from datetime import datetime, timezone

with open("scratch/probe_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

for resp in responses:
    url = resp.get("url", "")
    if "KHsBRRvjYL/charts?series=returns" in url:
        times = resp.get("data", {}).get("data", {}).get("times", [])
        dates = [datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%d') for t in times]
        train_dates = [d for d in dates if d <= '2023-01-01']
        print(f"Total chart dates: {len(dates)}")
        print(f"Train chart dates: {len(train_dates)}")
        break
