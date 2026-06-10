import json
import os
from datetime import datetime, timezone

paths = ["scratch/tabs_captured_responses.json", "scratch/probe_captured_responses.json"]

found = False
for path in paths:
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        responses = json.load(f)

    for resp in responses:
        url = resp.get("url", "")
        if "charts" in url:
            data = resp.get("data", {}).get("data", {})
            times = data.get("times", [])
            values = data.get("values", [])
            if len(times) > 100:
                print(f"Found charts in {path} at {url} with {len(times)} times.")
                for i in range(min(40, len(times))):
                    t = times[i]
                    val = values[i]
                    dt_utc = datetime.fromtimestamp(t, timezone.utc)
                    dt_local = datetime.fromtimestamp(t)
                    print(f"Index {i:2d}: Epoch {t} -> UTC: {dt_utc.strftime('%Y-%m-%d %H:%M:%S')} ({dt_utc.strftime('%a')}), Local: {dt_local.strftime('%Y-%m-%d %H:%M:%S')} ({dt_local.strftime('%a')}) -> Value: {val}")
                found = True
                break
    if found:
        break
