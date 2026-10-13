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

def run_tests():
    print("=== INDEPENDENT MATHEMATICAL & EDGE-CASE EQUIVALENCE TEST ===")
    np.random.seed(123)
    
    # 1. Clean series test (1000 bars, window 15)
    x_clean = pd.Series(100.0 + np.cumsum(np.random.randn(1000)))
    y_clean = pd.Series(50.0 + np.cumsum(np.random.randn(1000)))
    d = 15
    
    funcs = [
        ("ts_mean", ts_mean, naive_ts_mean),
        ("ts_sum", ts_sum, naive_ts_sum),
        ("ts_max", ts_max, naive_ts_max),
        ("ts_min", ts_min, naive_ts_min),
        ("ts_rank", ts_rank, naive_ts_rank),
        ("ts_corr", lambda s, w: ts_corr(s, y_clean, w), lambda s, w: naive_ts_corr(s, y_clean, w)),
        ("ts_zscore", ts_zscore, naive_ts_zscore),
        ("ts_argmax", ts_argmax, naive_ts_argmax),
        ("ts_argmin", ts_argmin, naive_ts_argmin),
    ]

    print("\n--- 1. Clean Series Equivalence (d=15, tolerance 1e-6) ---")
    for name, fast_f, naive_f in funcs:
        res_fast = fast_f(x_clean, d)
        res_naive = naive_f(x_clean, d)
        
        fast_arr = np.asarray(res_fast, dtype=np.float64)
        naive_arr = np.asarray(res_naive, dtype=np.float64)
        
        diff = np.abs(fast_arr - naive_arr)
        max_diff = np.nanmax(diff) if not np.all(np.isnan(diff)) else 0.0
        
        # Check nan masks match exactly
        nan_match = np.array_equal(np.isnan(fast_arr), np.isnan(naive_arr))
        
        # Check non-nan values within 1e-6
        close = np.allclose(fast_arr, naive_arr, rtol=1e-6, atol=1e-6, equal_nan=True)
        print(f"{name:<12}: Max Diff = {max_diff:.2e} | NaNs Match: {nan_match} | Close(1e-6): {close}")

    # 2. Window d = 1
    print("\n--- 2. Single Bar Window (d=1) ---")
    for name, fast_f, naive_f in funcs:
        res_fast = fast_f(x_clean, 1)
        res_naive = naive_f(x_clean, 1)
        fast_arr = np.asarray(res_fast, dtype=np.float64)
        naive_arr = np.asarray(res_naive, dtype=np.float64)
        close = np.allclose(fast_arr, naive_arr, rtol=1e-6, atol=1e-6, equal_nan=True)
        print(f"{name:<12}: Close(1e-6): {close}")

    # 3. Flat Series (Constant values e.g. 7.0)
    print("\n--- 3. Flat Series (Constant values) ---")
    x_flat = pd.Series(np.full(100, 7.0))
    y_flat = pd.Series(np.full(100, 3.0))
    for name, fast_f, naive_f in funcs:
        if name == "ts_corr":
            res_fast = ts_corr(x_flat, y_flat, 10)
            res_naive = naive_ts_corr(x_flat, y_flat, 10)
        else:
            res_fast = fast_f(x_flat, 10)
            res_naive = naive_f(x_flat, 10)
        fast_arr = np.asarray(res_fast, dtype=np.float64)
        naive_arr = np.asarray(res_naive, dtype=np.float64)
        close = np.allclose(fast_arr, naive_arr, rtol=1e-6, atol=1e-6, equal_nan=True)
        print(f"{name:<12}: Close(1e-6): {close} | Fast NaNs: {np.isnan(fast_arr).sum()} | Naive NaNs: {np.isnan(naive_arr).sum()}")

    # 4. Series with interior NaNs
    print("\n--- 4. Series with interior NaNs ---")
    x_nan = x_clean.copy()
    x_nan.iloc[10] = np.nan
    x_nan.iloc[15:18] = np.nan
    for name, fast_f, naive_f in funcs:
        if name == "ts_corr":
            res_fast = ts_corr(x_nan, y_clean, 10)
            res_naive = naive_ts_corr(x_nan, y_clean, 10)
        else:
            res_fast = fast_f(x_nan, 10)
            res_naive = naive_f(x_nan, 10)
        fast_arr = np.asarray(res_fast, dtype=np.float64)
        naive_arr = np.asarray(res_naive, dtype=np.float64)
        close = np.allclose(fast_arr, naive_arr, rtol=1e-6, atol=1e-6, equal_nan=True)
        print(f"{name:<12}: Close(1e-6): {close}")

    # 5. Small N (N=1, d=1 and N=1, d=5)
    print("\n--- 5. Single Value Array (N=1) ---")
    x_single = pd.Series([42.0])
    for name, fast_f, naive_f in funcs:
        if name == "ts_corr":
            res_fast = ts_corr(x_single, pd.Series([10.0]), 1)
            res_naive = naive_ts_corr(x_single, pd.Series([10.0]), 1)
        else:
            res_fast = fast_f(x_single, 1)
            res_naive = naive_f(x_single, 1)
        fast_arr = np.asarray(res_fast, dtype=np.float64)
        naive_arr = np.asarray(res_naive, dtype=np.float64)
        close = np.allclose(fast_arr, naive_arr, rtol=1e-6, atol=1e-6, equal_nan=True)
        print(f"{name:<12} (d=1, N=1): Fast={fast_arr}, Naive={naive_arr}, Close: {close}")

if __name__ == "__main__":
    run_tests()
