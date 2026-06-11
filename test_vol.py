import pandas as pd
from run_backtest import compute_metrics, print_report
from backtest.engine import XNOBacktestEngine, load_data
from xno_sdk.engine import SimpleAlgorithm

class VolumeTest(SimpleAlgorithm):
    def __algorithm__(self):
        v = self.data.pv_volume
        self.set_positions(v > 10, position=1.0)
        self.set_positions(v < 10, position=0.0)

print("Loading 10m data...")
df = load_data('10m')
engine = XNOBacktestEngine()
strategy = VolumeTest()
print("Running VolumeTest...")
result = engine.run(strategy, df)
metrics = compute_metrics(result)
print_report(result)
