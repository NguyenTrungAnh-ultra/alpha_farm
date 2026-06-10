import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data

df = load_data('10m')
print("Dates:")
dates = df.index.normalize().unique()
for d in dates[:5]:
    subset = df[df.index.normalize() == d]
    print(f"Date: {d.strftime('%Y-%m-%d')} ({d.strftime('%a')}) -> {len(subset)} bars")
