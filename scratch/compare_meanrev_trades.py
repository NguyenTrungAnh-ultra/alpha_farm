import sys
import os
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from scratch.run_local_meanrev import MeanRev_CCI_LinearReg

# Load web trades
web_path = "scratch/web_trades_meanrev.json"
if not os.path.exists(web_path):
    print("Web trades JSON not found yet.")
    sys.exit(1)

with open(web_path, "r", encoding="utf-8") as f:
    web_data = json.load(f)

web_trades = web_data.get("data", [])
if web_trades is None:
    print("No trades found in web response.")
    sys.exit(1)

print(f"Total web trades fetched: {len(web_trades)}")

# Run local Train stage backtest
df = load_data('30m', start='2020-01-01', end='2022-12-31')
engine = XNOBacktestEngine()
res = engine.run(MeanRev_CCI_LinearReg(), df)

local_trades = res.trades
print(f"Total local trades generated: {len(local_trades)}")

# Print first 5 trades from both
print("\n--- First 5 Web Trades ---")
for i, t in enumerate(web_trades[:5]):
    # Web fields might be different, let's print the dict
    print(f"Web {i+1}: {t}")

print("\n--- First 5 Local Trades ---")
for i, t in enumerate(local_trades[:5]):
    print(f"Local {i+1}: Entry={t.entry_time} Price={t.entry_price} -> Exit={t.exit_time} Price={t.exit_price} NetPnL={t.net_pnl:,.2f}")
