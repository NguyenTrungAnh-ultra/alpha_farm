import json
import os

paths = ["scratch/tabs_captured_responses.json", "scratch/probe_captured_responses.json"]

all_urls = set()
for path in paths:
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        responses = json.load(f)

    for resp in responses:
        all_urls.add(resp.get("url", ""))

print(f"Total unique URLs captured: {len(all_urls)}")
for url in sorted(list(all_urls)):
    print(url)
