import json
import os

paths = ["scratch/tabs_captured_responses.json", "scratch/probe_captured_responses.json"]

found = False
for path in paths:
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        responses = json.load(f)

    for resp in responses:
        url = resp.get("url", "")
        if "strategies/KHsBRRvjYL" in url and "charts" not in url and "stages" not in url:
            data = resp.get("data", {}).get("data", {})
            out_path = "scratch/strategy_KHsBRRvjYL.txt"
            with open(out_path, "w", encoding="utf-8") as out:
                out.write(f"Name: {data.get('name')}\n")
                out.write(f"Code:\n{data.get('code')}\n")
            print(f"Details written to {out_path}")
            found = True
            break
    if found:
        break
