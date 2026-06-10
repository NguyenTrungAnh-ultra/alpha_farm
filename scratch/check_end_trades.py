import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from backtest.runner import SMA_StopAndReverse

df = load_data('10m')
engine = XNOBacktestEngine()
res = engine.run(SMA_StopAndReverse(), df)

print(f"Total completed trades: {len(res.trades)}")
print(f"Last 5 completed trades:")
for i, t in enumerate(res.trades[-5:]):
    print(f"  Trade {len(res.trades)-4+i}: {t}")

print(f"\nLast 15 rows of positions and close prices:")
print(pd.DataFrame({
    'Close': df['Close'].iloc[-15:],
    'Position': res.positions.iloc[-15:]
}))
