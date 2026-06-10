import json
from datetime import datetime

def scan_file(path):
    print(f"\nScanning {path}...")
    with open(path, "r", encoding="utf-8") as f:
        responses = json.load(f)

    for idx, resp in enumerate(responses):
        url = resp.get("url", "")
        data = resp.get("data", {})
        if not isinstance(data, dict):
            continue
            
        # Let's search recursively for keys like 'times', 'dates', 'pnls', 'equity'
        def find_arrays(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    find_arrays(v, prefix + "." + k if prefix else k)
            elif isinstance(obj, list):
                if len(obj) > 100:
                    print(f"  [{idx}] URL: {url} -> Found large list at '{prefix}' (len={len(obj)})")
                    # Try to print first 5 elements
                    sample = obj[:5]
                    print(f"    Sample: {sample}")
                    if isinstance(sample[0], (int, float)):
                        try:
                            # Check if it looks like unix timestamp
                            if sample[0] > 1000000000 and sample[0] < 2000000000:
                                dts = [datetime.fromtimestamp(x).strftime('%Y-%m-%d') for x in sample]
                                print(f"    As Dates: {dts}")
                        except:
                            pass
        find_arrays(data)

scan_file("scratch/tabs_captured_responses.json")
scan_file("scratch/probe_captured_responses.json")
