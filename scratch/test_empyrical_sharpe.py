import json
import os
import numpy as np

# Load returns of KHsBRRvjYL (Train)
with open("scratch/probe_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

returns_list = []
for resp in responses:
    if "KHsBRRvjYL/charts?series=returns" in resp.get("url", ""):
        returns_list = resp.get("data", {}).get("data", {}).get("values", [])
        break

# Slice to the Train stage (first 748 elements)
returns = np.array(returns_list)[:748]

# Standard empyrical formula: mean / std(ddof=1) * np.sqrt(252)
mean = np.mean(returns)
std_sample = np.std(returns, ddof=1)
sharpe_empyrical = mean / std_sample * np.sqrt(252)

print(f"Empyrical Sharpe: {sharpe_empyrical:.8f} (XNO Target: 1.78111645)")

# Wait, what if they calculate the mean of daily returns excluding zeros?
non_zero = returns[returns != 0]
if len(non_zero) > 1:
    mean_nz = np.mean(non_zero)
    std_nz = np.std(non_zero, ddof=1)
    print(f"Sharpe of non-zero returns: {mean_nz / std_nz * np.sqrt(252):.8f}")
    
# What if Sharpe is calculated as:
# Sharpe = CAGR / (daily_std * np.sqrt(252))?
# Let's check this for KHsBRRvjYL:
cagr = 0.30651551799032895
vol = np.std(returns, ddof=1) * np.sqrt(252)
print(f"Sharpe (CAGR / Vol): {cagr / vol:.8f}")
