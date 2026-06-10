import json
import numpy as np
import pandas as pd
import sys

# Load web series
with open("scratch/probe_captured_responses.json", "r", encoding="utf-8") as f:
    responses = json.load(f)

web_pnls = []
web_returns = []
web_drawdowns = []

for resp in responses:
    url = resp.get("url", "")
    if "KHsBRRvjYL/charts?series=pnls" in url:
        web_pnls = np.array(resp.get("data", {}).get("data", {}).get("values", []))
    elif "KHsBRRvjYL/charts?series=returns" in url:
        web_returns = np.array(resp.get("data", {}).get("data", {}).get("values", []))
    elif "KHsBRRvjYL/charts?series=drawdown" in url:
        web_drawdowns = np.array(resp.get("data", {}).get("data", {}).get("values", []))

# Web performance metrics from meanrev_details.json
web_metrics = {
    "sharpe": 1.6322330739513347,
    "sortino": 2.847983627228581,
    "calmar": 1.8899325338866877,
    "omega": 1.6040962186105094,
    "profit_factor": 1.6040962186105094,
    "recovery_factor": 14.518408507473875,
    "volatility": 0.1350891804215193,
    "var": -0.013157403481526286,
    "cvar": -0.017531716021658143,
    "ulcer_index": 0.029512098883525094,
    "avg_return": 0.001434908058979533,
    "annual_return": 0.22458817027950917
}

initial = 1e9

# Let's compute different daily returns versions:
# 1. pct_change on equity (from web_pnls + 1e9)
equity = web_pnls + initial
pct_change_returns = np.diff(equity, prepend=initial) / (equity - np.diff(equity, prepend=0.0)) # rolling
# Wait, let's just use pct_change:
returns_rolling = pd.Series(equity).pct_change().fillna(0.0).values
returns_const = np.diff(equity, prepend=initial) / initial

# Let's test Sharpe ratio on both
print("=== Sharpe Ratio ===")
for label, r in [("Web Returns series", web_returns), ("Rolling returns", returns_rolling), ("Constant returns", returns_const)]:
    for ddof in [0, 1]:
        mean = np.mean(r)
        std = np.std(r, ddof=ddof)
        sharpe = mean / std * np.sqrt(252) if std > 0 else 0
        diff = abs(sharpe - web_metrics["sharpe"])
        print(f"  {label} (ddof={ddof}): {sharpe:.8f} (diff={diff:.8e})")

# Let's test Volatility
print("\n=== Volatility ===")
for label, r in [("Web Returns series", web_returns), ("Rolling returns", returns_rolling), ("Constant returns", returns_const)]:
    for ddof in [0, 1]:
        std = np.std(r, ddof=ddof)
        vol = std * np.sqrt(252)
        diff = abs(vol - web_metrics["volatility"])
        print(f"  {label} (ddof={ddof}): {vol:.8f} (diff={diff:.8e})")

# Let's test Sortino ratio
print("\n=== Sortino ===")
for label, r in [("Web Returns series", web_returns), ("Rolling returns", returns_rolling), ("Constant returns", returns_const)]:
    for ddof in [0, 1]:
        mean = np.mean(r)
        downside = r[r < 0]
        downside_std = np.std(downside, ddof=ddof) if len(downside) > 0 else 0
        sortino = mean / downside_std * np.sqrt(252) if downside_std > 0 else 0
        diff = abs(sortino - web_metrics["sortino"])
        print(f"  {label} (ddof={ddof}): {sortino:.8f} (diff={diff:.8e})")

# Let's test Average Return (avg_return)
print("\n=== Average Return ===")
for label, r in [("Web Returns series", web_returns), ("Rolling returns", returns_rolling), ("Constant returns", returns_const)]:
    mean = np.mean(r)
    diff = abs(mean - web_metrics["avg_return"])
    print(f"  {label}: {mean:.8f} (diff={diff:.8e})")

# Let's test VaR
print("\n=== VaR ===")
for label, r in [("Web Returns series", web_returns), ("Rolling returns", returns_rolling), ("Constant returns", returns_const)]:
    for ddof in [0, 1]:
        mean = np.mean(r)
        std = np.std(r, ddof=ddof)
        # 95% Parametric VaR formula: mean - 1.64485 * std
        var = mean - 1.6448536269514722 * std
        diff = abs(var - web_metrics["var"])
        print(f"  {label} (ddof={ddof}): {var:.8f} (diff={diff:.8e})")

# Let's test CVaR
print("\n=== CVaR ===")
for label, r in [("Web Returns series", web_returns), ("Rolling returns", returns_rolling), ("Constant returns", returns_const)]:
    # Historical CVaR at 95%
    threshold = np.percentile(r, 5)
    cvar = r[r <= threshold].mean()
    diff = abs(cvar - web_metrics["cvar"])
    print(f"  {label}: {cvar:.8f} (diff={diff:.8e})")

# Let's test Ulcer Index
print("\n=== Ulcer Index ===")
# Drawdown can be calculated from web_drawdowns (which is negative) or from equity
rolling_max = pd.Series(equity).cummax()
dd_calc = (equity - rolling_max) / rolling_max
ulcer_web = np.sqrt((web_drawdowns ** 2).mean())
ulcer_calc = np.sqrt((dd_calc ** 2).mean())
print(f"  Web UI: {ulcer_web:.8f} (diff={abs(ulcer_web - web_metrics['ulcer_index']):.8e})")
print(f"  Calc UI: {ulcer_calc:.8f} (diff={abs(ulcer_calc - web_metrics['ulcer_index']):.8e})")
