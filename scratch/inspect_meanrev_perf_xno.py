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
        if "strategies/KHsBRRvjYL" in url and "summary-aggregate" in url:
            print(f"\nFound summary-aggregate response in {path}: {url}")
            data = resp.get("data", {})
            print(json.dumps(data, indent=2, ensure_ascii=False))
