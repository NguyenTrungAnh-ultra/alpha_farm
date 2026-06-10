import json
import os

paths = ["scratch/tabs_captured_responses.json", "scratch/probe_captured_responses.json"]

for path in paths:
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        responses = json.load(f)

    for resp in responses:
        url = resp.get("url", "")
        if "summary-table" in url:
            print(f"Found summary-table URL in {path}: {url}")
            data = resp.get("data", {})
            print(f"Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            if isinstance(data, dict) and "data" in data:
                sub = data["data"]
                if isinstance(sub, list) and len(sub) > 0:
                    print(f"First element: {sub[0]}")
