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
        if "strategies/KHsBRRvjYL" in url and "charts" not in url and "stages" not in url and "progress" not in url:
            data = resp.get("data", {})
            out_path = "scratch/meanrev_details.json"
            with open(out_path, "w", encoding="utf-8") as out:
                json.dump(data, out, indent=2, ensure_ascii=False)
            print(f"Details written to {out_path}")
            found = True
            break
    if found:
        break
