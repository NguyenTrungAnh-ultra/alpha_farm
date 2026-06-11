import os
import sys
import pandas as pd
from run_backtest import compute_metrics
from backtest.engine import XNOBacktestEngine, load_data

sys.path.insert(0, os.path.abspath('agent/results'))

df_10m = load_data('10m')
engine = XNOBacktestEngine()

results = []
for file in os.listdir('agent/results'):
    if file.endswith('_10m.py'):
        mod_name = file[:-3]
        try:
            mod = __import__(mod_name)
            strategy = mod.CustomStrategy()
            res = engine.run(strategy, df_10m)
            metrics = compute_metrics(res)
            print(f"{mod_name}: Ret={metrics['cumulative_return']:.2f}%, Sharpe={metrics['sharpe_ratio']:.2f}, MDD={metrics['max_drawdown']:.2f}%")
        except Exception as e:
            print(f"Error running {mod_name}: {e}")
