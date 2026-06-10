import json
import os
import numpy as np

with open("scratch/probe_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

returns_list = []
for resp in responses:
    if "KHsBRRvjYL/charts?series=returns" in resp.get("url", ""):
        returns_list = resp.get("data", {}).get("data", {}).get("values", [])
        break

target = 1.7811164461743403

for N in range(745, 756):
    returns = np.array(returns_list)[:N]
    mean = np.mean(returns)
    std_p = np.std(returns, ddof=0)
    std_s = np.std(returns, ddof=1)
    
    factor_p = target / (mean / std_p) if mean != 0 else 0
    print(f"N={N}: Mean={mean:.8f}, Std(pop)={std_p:.8f}, Required Factor={factor_p:.6f} (squared={factor_p**2:.2f})")
