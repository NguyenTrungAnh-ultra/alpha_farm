import json
import os
import numpy as np

# Load XNO charts for KHsBRRvjYL
with open("scratch/probe_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

xno_returns = []
for resp in responses:
    url = resp.get("url", "")
    if "KHsBRRvjYL/charts?series=returns" in url:
        xno_returns = resp.get("data", {}).get("data", {}).get("values", [])
        break

print(f"Loaded {len(xno_returns)} returns.")
if not xno_returns:
    print("No returns found.")
    exit(1)

returns = np.array(xno_returns)

# 1. Historical VaR/CVaR (95%)
# Percentile 5 of returns
hist_var = np.percentile(returns, 5)
hist_cvar = returns[returns <= hist_var].mean()

# 2. Parametric VaR/CVaR (95%)
mean = np.mean(returns)
std = np.std(returns, ddof=0)
z_95 = 1.6448536269514722
param_var = mean - z_95 * std

import scipy.stats as stats
pdf_z = stats.norm.pdf(z_95)
param_cvar = mean - (pdf_z / 0.05) * std

print("\nXNO Target Values:")
print("  VaR:  -0.01315740")
print("  CVaR: -0.01753172")

print("\nHistorical VaR/CVaR (95%):")
print(f"  VaR:  {hist_var:.8f}")
print(f"  CVaR: {hist_cvar:.8f}")

print("\nParametric VaR/CVaR (95%):")
print(f"  VaR:  {param_var:.8f}")
print(f"  CVaR: {param_cvar:.8f}")

# Let's test percentile methods for VaR: linear, lower, higher, midpoint, nearest
for method in ['linear', 'lower', 'higher', 'midpoint', 'nearest']:
    var_m = np.percentile(returns, 5, method=method)
    cvar_m = returns[returns <= var_m].mean()
    print(f"Method '{method}': VaR={var_m:.8f}, CVaR={cvar_m:.8f}")
