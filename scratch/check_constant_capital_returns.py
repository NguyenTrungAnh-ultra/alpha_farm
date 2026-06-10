import json
import os
import numpy as np

with open("scratch/probe_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

pnls_list = []
for resp in responses:
    if "KHsBRRvjYL/charts?series=pnls" in resp.get("url", ""):
        pnls_list = resp.get("data", {}).get("data", {}).get("values", [])
        break

if not pnls_list:
    print("No pnls found.")
    exit(1)

# Slice to Train stage (751 days)
pnls = np.array(pnls_list)[:751]

# Reconstruct daily PNL changes
pnl_changes = np.diff(pnls, prepend=0.0)

# Calculate daily returns as: pnl_change / 1,000,000,000
const_returns = pnl_changes / 1e9

mean = np.mean(const_returns)
std_p = np.std(const_returns, ddof=0)
std_s = np.std(const_returns, ddof=1)

print(f"Mean: {mean:.12f}")
print(f"Std (pop): {std_p:.12f}")

# Target Sharpe is 1.7811164461743403
target = 1.7811164461743403

# Check standard factors
print(f"Sharpe with sqrt(252), pop: {mean / std_p * np.sqrt(252):.8f}")
print(f"Sharpe with sqrt(252), sample: {mean / std_s * np.sqrt(252):.8f}")

# Solve for factor
factor = target / (mean / std_p)
print(f"Required factor (pop): {factor:.6f} (squared: {factor**2:.2f})")
