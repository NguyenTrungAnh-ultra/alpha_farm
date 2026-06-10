import json

with open("scratch/charts_sma10.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Main keys:", list(data.keys()))
for k, v in data.items():
    if isinstance(v, dict):
        print(f"Sub-keys of {k}:", list(v.keys()))
        if "data" in v:
            d = v["data"]
            if isinstance(d, dict):
                print(f"  data keys of {k}:", list(d.keys()))
            else:
                print(f"  data of {k} is:", type(d))
