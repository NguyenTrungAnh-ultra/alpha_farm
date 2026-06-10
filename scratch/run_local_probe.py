import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from xno_sdk.engine import SimpleAlgorithm

df = load_data('10m', start='2020-01-01', end='2022-12-31')

class Probe(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        is_first_bar = self.op.isna(self.op.shift(close, 1))
        index_series = self.op.bars_since(is_first_bar)
        mask = (index_series >= 100) & (index_series <= 105)
        self.set_positions(mask, position=1.0)

engine = XNOBacktestEngine()
res = engine.run(Probe(), df)

print('Total Trades:', res.total_trades)
print('Fees:', res.total_fees)
print('Final Equity:', res.final_equity)
print('Net Return:', (res.final_equity - 1e9)/1e9)
print('\nTrades list:')
for t in res.trades:
    print(t)
