import json
import os

path = "scratch/tabs_captured_responses.json"
if not os.path.exists(path):
    path = "scratch/probe_captured_responses.json"

if not os.path.exists(path):
    print(f"File {path} not found.")
    exit(1)

with open(path, "r", encoding="utf-8") as f:
    responses = json.load(f)

for idx, resp in enumerate(responses):
    url = resp.get("url", "")
    data = resp.get("data", {})
    if not isinstance(data, dict):
        continue
        
    if "performance" in url or "evaluations" in url:
        print(f"\n==========================================")
        print(f"[{idx}] URL: {url}")
        # Print nested dictionary in formatted JSON
        print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
