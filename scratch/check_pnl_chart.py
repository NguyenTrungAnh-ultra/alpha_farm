import os
import json
import datetime

json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "tabs_captured_responses.json")

with open(json_path, "r", encoding="utf-8") as f:
    responses = json.load(f)

for resp in responses:
    if "charts" in resp["url"] and "series=pnls" in resp["url"]:
        chart_data = resp["data"]["data"]
        times = chart_data["times"]
        values = chart_data["values"]
        
        print(f"Total points: {len(times)}")
        print("Non-zero PnL changes:")
        last_val = 0
        for t, v in zip(times, values):
            dt = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%d')
            if v != last_val:
                print(f"Date: {dt}, PnL: {v:,.2f}, Change: {v - last_val:,.2f}")
                last_val = v
