import json
import os
import numpy as np

with open("scratch/probe_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

xno_returns = []
for resp in responses:
    if "KHsBRRvjYL/charts?series=returns" in resp.get("url", ""):
        xno_returns = resp.get("data", {}).get("data", {}).get("values", [])
        break

returns = np.array(xno_returns)

hist_var = np.percentile(returns, 5)
param_var = np.mean(returns) - 1.6448536269514722 * np.std(returns, ddof=0)

cvar_with_hist_threshold = returns[returns <= hist_var].mean()
cvar_with_param_threshold = returns[returns <= param_var].mean()

print(f"XNO CVaR Target: -0.01753172")
print(f"CVaR with historical VaR threshold: {cvar_with_hist_threshold:.8f}")
print(f"CVaR with parametric VaR threshold: {cvar_with_param_threshold:.8f}")
