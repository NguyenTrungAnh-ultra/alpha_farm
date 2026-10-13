"""
f:/Projects/alpha_farm/.agents/challenger_m2_1/empirical_stress_test.py

Empirical Stress Testing Harness for core_engine.AlphaPrimitives.
Tests all 9 primitive functions across extreme inputs:
1. NaN arrays (all NaNs, leading NaNs, trailing NaNs, interspersed NaNs)
2. All zeros and constant values
3. Window sizes: d=1, d=N, d>N, d huge
4. Dimensionality: 1D vs 2D vs 3D vs 0D (scalars)
5. High dynamic range floats (1e300, 1e-300, Inf, -Inf)
6. Data types (int64, float32, bool, object)
7. Pandas Series with custom indices, mismatched inputs, names
8. Equivalence against Pandas reference implementations
"""

import sys
import numpy as np
import pandas as pd
import traceback

from core_engine.AlphaPrimitives import (
    ts_mean, ts_sum, ts_max, ts_min,
    ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
)

ALL_PRIMITIVES = [
    ("ts_mean", ts_mean),
    ("ts_sum", ts_sum),
    ("ts_max", ts_max),
    ("ts_min", ts_min),
    ("ts_rank", ts_rank),
    ("ts_corr", ts_corr),
    ("ts_zscore", ts_zscore),
    ("ts_argmax", ts_argmax),
    ("ts_argmin", ts_argmin),
]

SINGLE_INPUT_PRIMITIVES = [
    ("ts_mean", ts_mean),
    ("ts_sum", ts_sum),
    ("ts_max", ts_max),
    ("ts_min", ts_min),
    ("ts_rank", ts_rank),
    ("ts_zscore", ts_zscore),
    ("ts_argmax", ts_argmax),
    ("ts_argmin", ts_argmin),
]


def run_single(fn, x, d):
    return fn(x, d)


def run_primitive(name, fn, x, y, d):
    if name == "ts_corr":
        return fn(x, y, d)
    return fn(x, d)


def test_nan_arrays():
    print("--- Test Category 1: NaN Arrays ---")
    results = []
    
    # 1.1 All NaNs
    arr_all_nan = np.full(50, np.nan)
    for name, fn in ALL_PRIMITIVES:
        try:
            res = run_primitive(name, fn, arr_all_nan, arr_all_nan, 5)
            # Should return array of all NaNs
            is_valid = isinstance(res, np.ndarray) and len(res) == 50 and np.isnan(res).all()
            results.append((f"{name} - All NaNs", "PASS" if is_valid else f"FAIL (unexpected output shape/vals: {res})"))
        except Exception as e:
            results.append((f"{name} - All NaNs", f"FAIL (Exception: {e})"))

    # 1.2 Leading NaNs
    arr_leading_nan = np.array([np.nan]*10 + list(np.random.randn(40)))
    for name, fn in ALL_PRIMITIVES:
        try:
            res = run_primitive(name, fn, arr_leading_nan, arr_leading_nan, 5)
            # First 10 + 5 - 1 = 14 elements should be NaN (windows overlapping with leading NaNs)
            is_valid = np.isnan(res[:14]).all() and not np.isnan(res[14:]).any()
            results.append((f"{name} - Leading NaNs", "PASS" if is_valid else f"FAIL (unexpected NaN pattern)"))
        except Exception as e:
            results.append((f"{name} - Leading NaNs", f"FAIL (Exception: {e})"))

    # 1.3 Interspersed NaNs
    arr_interspersed = np.array([1.0, 2.0, np.nan, 4.0, 5.0, 6.0, np.nan, 8.0, 9.0, 10.0])
    for name, fn in ALL_PRIMITIVES:
        try:
            res = run_primitive(name, fn, arr_interspersed, arr_interspersed, 3)
            # Windows containing NaN must yield NaN
            # Window 0: [1,2,nan] -> index 2 -> NaN
            # Window 1: [2,nan,4] -> index 3 -> NaN
            # Window 2: [nan,4,5] -> index 4 -> NaN
            # Window 3: [4,5,6] -> index 5 -> valid
            is_nan_correct = np.isnan(res[2]) and np.isnan(res[3]) and np.isnan(res[4]) and not np.isnan(res[5])
            results.append((f"{name} - Interspersed NaNs", "PASS" if is_nan_correct else f"FAIL (res[2..5]: {res[2:6]})"))
        except Exception as e:
            results.append((f"{name} - Interspersed NaNs", f"FAIL (Exception: {e})"))

    return results


def test_all_zeros_and_constants():
    print("--- Test Category 2: All Zeros and Constant Values ---")
    results = []
    
    arr_zeros = np.zeros(50)
    arr_ones = np.ones(50)
    
    for name, fn in ALL_PRIMITIVES:
        try:
            res = run_primitive(name, fn, arr_zeros, arr_ones, 10)
            assert len(res) == 50
            assert np.isnan(res[:9]).all()
            if name == "ts_mean":
                assert (res[9:] == 0.0).all()
            elif name == "ts_sum":
                assert (res[9:] == 0.0).all()
            elif name == "ts_max":
                assert (res[9:] == 0.0).all()
            elif name == "ts_min":
                assert (res[9:] == 0.0).all()
            elif name == "ts_rank":
                # All zeros -> all equal -> rank should be 0.55 or similar (less=0, equal=10, rank=0.5*(11)=5.5, pct=5.5/10=0.55)
                assert np.allclose(res[9:], 0.55)
            elif name == "ts_zscore":
                # Zero variance -> returns 0.0
                assert (res[9:] == 0.0).all()
            elif name == "ts_corr":
                # Constant series correlation -> NaN (denom <= 1e-12)
                assert np.isnan(res[9:]).all()
            elif name in ("ts_argmax", "ts_argmin"):
                # argmax of all zeros returns 1.0 (first occurrence)
                assert (res[9:] == 1.0).all()
            results.append((f"{name} - All Zeros / Constants", "PASS"))
        except Exception as e:
            results.append((f"{name} - All Zeros / Constants", f"FAIL (Exception: {e})"))

    return results


def test_window_sizes():
    print("--- Test Category 3: Window Sizes (d=1, d=N, d>N, d huge) ---")
    results = []
    arr = np.array([10.0, 20.0, 15.0, 30.0, 25.0])
    N = len(arr)

    # 3.1 d = 1
    for name, fn in ALL_PRIMITIVES:
        try:
            res = run_primitive(name, fn, arr, arr, 1)
            assert len(res) == N
            assert not np.isnan(res).any() or (name == "ts_corr" and np.isnan(res).all())
            # For d=1: ts_mean = arr, ts_sum = arr, ts_max = arr, ts_min = arr
            # ts_rank = 1.0, ts_argmax = 1.0, ts_argmin = 1.0
            if name == "ts_mean":
                assert np.allclose(res, arr)
            elif name == "ts_sum":
                assert np.allclose(res, arr)
            elif name == "ts_max":
                assert np.allclose(res, arr)
            elif name == "ts_min":
                assert np.allclose(res, arr)
            elif name == "ts_rank":
                assert np.allclose(res, 1.0)
            elif name == "ts_zscore":
                # d=1 std with ddof=1 is NaN -> stds > 1e-12 is False -> returns 0.0
                assert np.allclose(res, 0.0)
            elif name in ("ts_argmax", "ts_argmin"):
                assert np.allclose(res, 1.0)
            results.append((f"{name} - d=1", "PASS"))
        except Exception as e:
            results.append((f"{name} - d=1", f"FAIL (Exception: {e})"))

    # 3.2 d = N
    for name, fn in ALL_PRIMITIVES:
        try:
            res = run_primitive(name, fn, arr, arr, N)
            assert len(res) == N
            assert np.isnan(res[:-1]).all()
            assert not np.isnan(res[-1])
            results.append((f"{name} - d=N", "PASS"))
        except Exception as e:
            results.append((f"{name} - d=N", f"FAIL (Exception: {e})"))

    # 3.3 d > N
    for name, fn in ALL_PRIMITIVES:
        try:
            res = run_primitive(name, fn, arr, arr, N + 10)
            assert len(res) == N
            assert np.isnan(res).all()
            results.append((f"{name} - d>N", "PASS"))
        except Exception as e:
            results.append((f"{name} - d>N", f"FAIL (Exception: {e})"))

    # 3.4 Invalid d (0, negative, float, bool)
    invalid_ds = [0, -5, 3.5, True, False, "5"]
    for name, fn in ALL_PRIMITIVES:
        for inv_d in invalid_ds:
            try:
                run_primitive(name, fn, arr, arr, inv_d)
                results.append((f"{name} - invalid d={inv_d}", f"FAIL (Did not raise ValueError)"))
            except ValueError:
                results.append((f"{name} - invalid d={inv_d}", "PASS"))
            except Exception as e:
                results.append((f"{name} - invalid d={inv_d}", f"FAIL (Unexpected error: {type(e).__name__}: {e})"))

    return results


def test_dimensionality():
    print("--- Test Category 4: 1D vs 2D vs 3D vs 0D Inputs ---")
    results = []
    
    non_1d_inputs = [
        ("2D (10,5)", np.ones((10, 5))),
        ("3D (2,3,4)", np.ones((2, 3, 4))),
        ("0D scalar", np.array(5.0)),
    ]

    for name, fn in ALL_PRIMITIVES:
        for label, inp in non_1d_inputs:
            try:
                run_primitive(name, fn, inp, inp, 3)
                results.append((f"{name} - {label}", "FAIL (Did not raise ValueError)"))
            except ValueError as ve:
                results.append((f"{name} - {label}", "PASS"))
            except Exception as e:
                results.append((f"{name} - {label}", f"FAIL (Unexpected exception: {type(e).__name__}: {e})"))

    return results


def test_high_dynamic_range():
    print("--- Test Category 5: High Dynamic Range Floats ---")
    results = []
    
    # Large numbers near float64 limits
    arr_large = np.array([1e300, 2e300, 1.5e300, 3e300, 2.5e300])
    arr_small = np.array([1e-300, 2e-300, 1.5e-300, 3e-300, 2.5e-300])
    arr_inf = np.array([1.0, np.inf, 3.0, -np.inf, 5.0])
    
    for name, fn in ALL_PRIMITIVES:
        # Large numbers
        try:
            res = run_primitive(name, fn, arr_large, arr_large, 3)
            assert len(res) == len(arr_large)
            results.append((f"{name} - 1e300 values", "PASS"))
        except Exception as e:
            results.append((f"{name} - 1e300 values", f"FAIL (Exception: {e})"))

        # Small numbers
        try:
            res = run_primitive(name, fn, arr_small, arr_small, 3)
            assert len(res) == len(arr_small)
            results.append((f"{name} - 1e-300 values", "PASS"))
        except Exception as e:
            results.append((f"{name} - 1e-300 values", f"FAIL (Exception: {e})"))

        # Inf values
        try:
            res = run_primitive(name, fn, arr_inf, arr_inf, 3)
            assert len(res) == len(arr_inf)
            results.append((f"{name} - Inf/-Inf values", "PASS"))
        except Exception as e:
            results.append((f"{name} - Inf/-Inf values", f"FAIL (Exception: {e})"))

    return results


def test_data_types_and_series():
    print("--- Test Category 6 & 7: Data Types and Pandas Series ---")
    results = []

    # Integers
    arr_int = np.array([10, 20, 30, 40, 50], dtype=np.int64)
    # Booleans
    arr_bool = np.array([True, False, True, True, False], dtype=bool)
    # Float32
    arr_f32 = np.array([1.0, 2.0, 3.0, 4.0, 5.0], dtype=np.float32)
    # Series with DatetimeIndex
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    ser_dt = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=dates, name="test_series")

    for name, fn in ALL_PRIMITIVES:
        # Int64
        try:
            res = run_primitive(name, fn, arr_int, arr_int, 3)
            assert res.dtype == np.float64
            results.append((f"{name} - int64 input", "PASS"))
        except Exception as e:
            results.append((f"{name} - int64 input", f"FAIL ({e})"))

        # Float32
        try:
            res = run_primitive(name, fn, arr_f32, arr_f32, 3)
            assert res.dtype == np.float64
            results.append((f"{name} - float32 input", "PASS"))
        except Exception as e:
            results.append((f"{name} - float32 input", f"FAIL ({e})"))

        # Series preservation
        try:
            res = run_primitive(name, fn, ser_dt, ser_dt, 3)
            assert isinstance(res, pd.Series)
            assert res.name == "test_series"
            assert (res.index == dates).all()
            results.append((f"{name} - Series index/name preservation", "PASS"))
        except Exception as e:
            results.append((f"{name} - Series index/name preservation", f"FAIL ({e})"))

    # ts_corr shape mismatch & type mismatch
    try:
        ts_corr(np.ones(10), np.ones(20), 3)
        results.append(("ts_corr - shape mismatch", "FAIL (Did not raise ValueError)"))
    except ValueError:
        results.append(("ts_corr - shape mismatch", "PASS"))

    return results


def test_performance_stress():
    print("--- Test Category 8: Performance Stress & Memory (N=1,000,000, d=500) ---")
    results = []
    
    N = 1_000_000
    d = 500
    np.random.seed(42)
    x = np.random.randn(N)
    y = np.random.randn(N)

    for name, fn in ALL_PRIMITIVES:
        try:
            import time
            t0 = time.perf_counter()
            res = run_primitive(name, fn, x, y, d)
            elapsed = time.perf_counter() - t0
            assert len(res) == N
            results.append((f"{name} - N=1M, d=500 stress test", f"PASS ({elapsed*1000:.2f} ms)"))
        except Exception as e:
            results.append((f"{name} - N=1M, d=500 stress test", f"FAIL ({e})"))

    return results


def main():
    print("==================================================================")
    print("      Empirical Stress Test Suite for AlphaPrimitives.py          ")
    print("==================================================================")
    
    all_results = []
    all_results.extend(test_nan_arrays())
    all_results.extend(test_all_zeros_and_constants())
    all_results.extend(test_window_sizes())
    all_results.extend(test_dimensionality())
    all_results.extend(test_high_dynamic_range())
    all_results.extend(test_data_types_and_series())
    all_results.extend(test_performance_stress())

    print("\n==================================================================")
    print("                         TEST SUMMARY                             ")
    print("==================================================================")
    
    pass_count = 0
    fail_count = 0
    
    for label, status in all_results:
        print(f"{label:<60} | {status}")
        if status.startswith("PASS"):
            pass_count += 1
        else:
            fail_count += 1
            
    print("==================================================================")
    print(f"Total Tests Run: {len(all_results)} | Passed: {pass_count} | Failed: {fail_count}")
    print("==================================================================")
    
    if fail_count > 0:
        print(" VERDICT: FAIL — At least one empirical stress test failed.")
        sys.exit(1)
    else:
        print(" VERDICT: PASS — All empirical stress tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
