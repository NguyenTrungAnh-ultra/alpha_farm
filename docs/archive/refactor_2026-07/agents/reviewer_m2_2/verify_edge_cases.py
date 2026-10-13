import numpy as np
import pandas as pd
from core_engine.AlphaPrimitives import (
    ts_mean, ts_sum, ts_max, ts_min,
    ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
)
from benchmark_primitives import (
    naive_ts_mean, naive_ts_sum, naive_ts_max, naive_ts_min,
    naive_ts_rank, naive_ts_corr, naive_ts_zscore, naive_ts_argmax, naive_ts_argmin
)

def test_ties():
    print("=== TIES TEST ===")
    # Array with duplicate max values
    x_ties = pd.Series([1.0, 5.0, 5.0, 2.0, 3.0, 5.0, 1.0])
    d = 4
    print("x:", list(x_ties))
    print("ts_argmax:", list(ts_argmax(x_ties, d)))
    print("naive_argmax:", list(naive_ts_argmax(x_ties, d)))
    
    print("ts_argmin:", list(ts_argmin(x_ties, d)))
    print("naive_argmin:", list(naive_ts_argmin(x_ties, d)))
    
    print("ts_rank:", list(ts_rank(x_ties, d)))
    print("naive_rank:", list(naive_ts_rank(x_ties, d)))

def test_nans_in_middle():
    print("\n=== NANS IN MIDDLE TEST ===")
    x_nan = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0, 6.0, 7.0])
    d = 3
    print("x:", list(x_nan))
    print("ts_mean:", list(ts_mean(x_nan, d)))
    print("naive_mean:", list(naive_ts_mean(x_nan, d)))
    
    print("ts_rank:", list(ts_rank(x_nan, d)))
    print("naive_rank:", list(naive_ts_rank(x_nan, d)))
    
    print("ts_argmax:", list(ts_argmax(x_nan, d)))
    print("naive_argmax:", list(naive_ts_argmax(x_nan, d)))

def test_d_larger_than_N():
    print("\n=== d > N TEST ===")
    x = pd.Series([1.0, 2.0, 3.0])
    d = 5
    print("ts_mean (d=5, N=3):", list(ts_mean(x, d)))

def test_invalid_d():
    print("\n=== INVALID d TEST ===")
    x = pd.Series([1.0, 2.0, 3.0])
    for invalid_d in [0, -1, 2.5, True, False, "3", None]:
        try:
            ts_mean(x, invalid_d)
            print(f"FAILED to raise error for d={invalid_d} ({type(invalid_d)})")
        except ValueError as e:
            print(f"PASSED raise error for d={invalid_d} ({type(invalid_d)}): {e}")

if __name__ == "__main__":
    test_ties()
    test_nans_in_middle()
    test_d_larger_than_N()
    test_invalid_d()
