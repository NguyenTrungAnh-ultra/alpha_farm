import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from backtest.runner import SMA_StopAndReverse

df = load_data('10m')
print(f"Data range: {df.index[0]} to {df.index[-1]}")
print(f"Total bars: {len(df)}")

engine = XNOBacktestEngine()
res = engine.run(SMA_StopAndReverse(), df)

print("\n--- Local Backtest Results ---")
print(f"Total Trades count field: {res.total_trades}")
print(f"Number of completed trades: {len(res.trades)}")
print(f"Total fees: {res.total_fees:,.2f}")
print(f"Initial capital: {res.initial_capital:,.2f}")
print(f"Final equity: {res.final_equity:,.2f}")

# Find first few trades
print("\nFirst 5 trades:")
for i, t in enumerate(res.trades[:5]):
    print(f"Trade {i+1}: Entry Bar {t.entry_bar} ({t.entry_time}) Price {t.entry_price} -> Exit Bar {t.exit_bar} ({t.exit_time}) Price {t.exit_price}, Contracts {t.contracts}, Fee {t.fee:,.2f}, Net PnL {t.net_pnl:,.2f}")

# Find last few trades
print("\nLast 5 trades:")
for i, t in enumerate(res.trades[-5:]):
    print(f"Trade {len(res.trades)-4+i}: Entry Bar {t.entry_bar} ({t.entry_time}) Price {t.entry_price} -> Exit Bar {t.exit_bar} ({t.exit_time}) Price {t.exit_price}, Contracts {t.contracts}, Fee {t.fee:,.2f}, Net PnL {t.net_pnl:,.2f}")
