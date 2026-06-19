import sys
sys.path.insert(0, 'f:/Projects/alpha_farm')
from strategy_workflows.SubmitStrategies import run_auto_submit

with open('f:/Projects/alpha_farm/results/failed/Micro_T3_ADX_Burst_Scalper_1m.py', 'r', encoding='utf-8') as f:
    code = f.read()

success, err = run_auto_submit(code, '1m', timeout_seconds=120)
print("SUCCESS:", success)
print("ERROR MSG:", err)
