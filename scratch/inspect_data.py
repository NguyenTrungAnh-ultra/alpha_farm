import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data

df = load_data('10m')

print("Index, Datetime, Open, High, Low, Close")
for i in [99, 100, 101, 102, 103, 104, 105, 106, 107]:
    row = df.iloc[i]
    print(f"{i}, {df.index[i]}, {row['Open']}, {row['High']}, {row['Low']}, {row['Close']}")
