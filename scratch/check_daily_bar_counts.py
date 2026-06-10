import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data

df = load_data('10m')
counts = df.groupby(df.index.date).size()

print(f"Total days: {len(counts)}")
print(f"Days with exactly 27 bars: {sum(counts == 27)}")
print(f"Days with other bar counts:")
other_counts = counts[counts != 27]
for date, count in other_counts.items():
    print(f"  {date} -> {count} bars")
