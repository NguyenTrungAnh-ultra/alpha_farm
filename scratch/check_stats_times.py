import json
from datetime import datetime

with open("scratch/tabs_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

for resp in responses:
    if "stats/performance" in resp.get("url", ""):
        times = resp.get("data", {}).get("times", [])
        print(f"Stats/performance: {len(times)} times.")
        if times:
            print("First 10 times:")
            for t in times[:10]:
                dt = datetime.fromtimestamp(t)
                print(f"  {t} -> {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print("Last 5 times:")
            for t in times[-5:]:
                dt = datetime.fromtimestamp(t)
                print(f"  {t} -> {dt.strftime('%Y-%m-%d %H:%M:%S')}")
