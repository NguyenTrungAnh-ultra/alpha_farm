import pandas as pd
from run_backtest import compute_metrics, print_report
from backtest.engine import XNOBacktestEngine, load_data
import sys
import os

sys.path.insert(0, os.path.abspath('agent/results'))
from MeanRev_CCI_LinearReg_30m import CustomStrategy

print("Loading 30m data...")
df = load_data('30m')
engine = XNOBacktestEngine()
strategy = CustomStrategy()
print("Running MeanRev_CCI_LinearReg_30m...")
result = engine.run(strategy, df)
metrics = compute_metrics(result)
print_report(result)
