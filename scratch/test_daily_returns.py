import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from xno_sdk.engine import SimpleAlgorithm

class Probe(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        is_first_bar = self.op.isna(self.op.shift(close, 1))
        index_series = self.op.bars_since(is_first_bar)
        mask = (index_series >= 100) & (index_series <= 105)
        self.set_positions(mask, position=1.0)

df = load_data('10m', start='2020-01-01', end='2022-12-31')
engine = XNOBacktestEngine()
res = engine.run(Probe(), df)

# Local 10-minute equity curve
equity = res.equity_curve

# Resample to daily (taking the last bar of each day)
# In Vietnam, trading hours are 9:00 to 14:46. So the last bar of the day is around 14:30 or 14:40.
daily_equity = equity.resample('D').last().dropna()
print(f"Number of daily equity days: {len(daily_equity)}")

# Let's print first 10 daily equities
for i in range(10):
    print(f"Day {i}: Date {daily_equity.index[i].strftime('%Y-%m-%d')} -> Equity {daily_equity.iloc[i]:,.2f}")

# Calculate daily returns
# Wait! How is the return of the first day computed?
# If the first day's return is 0, let's see.
# If we calculate percentage change of daily_equity:
daily_returns = daily_equity.pct_change()
# For the first element, pct_change is NaN, which we can fill with 0.0
daily_returns = daily_returns.fillna(0.0)

print("\nFirst 10 daily returns:")
for i in range(10):
    print(f"Day {i}: Date {daily_equity.index[i].strftime('%Y-%m-%d')} -> Return {daily_returns.iloc[i]:.8f}")
