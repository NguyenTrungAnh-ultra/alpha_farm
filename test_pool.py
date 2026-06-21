import pickle
import pandas as pd
import numpy as np
from strategy_workflows.RunMCTS import process_timeframe

if __name__ == '__main__':
    # Mocking successful candidate
    df = pd.Series([1.0, 2.0], index=pd.date_range('2020-01-01', periods=2))
    res = ('30m', 100, 99, [{
        'expr': 'mock',
        'metrics': {'win': np.int64(1)},
        'equity_curve': df,
        'positions': df
    }])
    print("Execution done. Pickling...")
    try:
        data = pickle.dumps(res)
        print("Pickle successful, length:", len(data))
    except Exception as e:
        print("Pickle failed:", e)
