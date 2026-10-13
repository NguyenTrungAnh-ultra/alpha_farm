"""
f:/Projects/alpha_farm/.agents/teamwork_preview_challenger_m2_1/empirical_stress_test.py

Empirical stress testing harness for core_engine.AlphaPrimitives.
Evaluates numerical correctness, edge case handling, and pandas equivalence.
"""

import sys
import numpy as np
import pandas as pd

# Import primitives from repository root
sys.path.insert(0, "f:/Projects/alpha_farm")
from core_engine.AlphaPrimitives import (
    ts_mean, ts_sum, ts_max, ts_min,
    ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
)


def naive_ts_rank(x: pd.Series, d: int) -> pd.Series:
    def _rank_last(w: pd.Series) -> float:
        if w.isna().any():
            return np.nan
        return float(w.rank(pct=True).iloc[-1])
    return x.rolling(window=d, min_periods=d).apply(_rank_last, raw=False)


def run_all_tests() -> dict:
    results = {}
    
    # -------------------------------------------------------------
    # 1. Standard Equivalence Test
    # -------------------------------------------------------------
    np.random.seed(42)
    n = 100
    d = 10
    dates = pd.date_range("2024-01-01", periods=n, freq="1h")
    s_x = pd.Series(100.0 + np.cumsum(np.random.randn(n)), index=dates, name="x")
    s_y = pd.Series(50.0 + np.cumsum(np.random.randn(n)), index=dates, name="y")

    # ts_mean
    eq_mean = np.allclose(ts_mean(s_x, d), s_x.rolling(d, min_periods=d).mean(), equal_nan=True)
    # ts_sum
    eq_sum = np.allclose(ts_sum(s_x, d), s_x.rolling(d, min_periods=d).sum(), equal_nan=True)
    # ts_max
    eq_max = np.allclose(ts_max(s_x, d), s_x.rolling(d, min_periods=d).max(), equal_nan=True)
    # ts_min
    eq_min = np.allclose(ts_min(s_x, d), s_x.rolling(d, min_periods=d).min(), equal_nan=True)
    # ts_rank
    eq_rank = np.allclose(ts_rank(s_x, d), naive_ts_rank(s_x, d), equal_nan=True)
    # ts_corr
    eq_corr = np.allclose(ts_corr(s_x, s_y, d), s_x.rolling(d, min_periods=d).corr(s_y), equal_nan=True)
    # ts_zscore
    ref_z = (s_x - s_x.rolling(d, min_periods=d).mean()) / s_x.rolling(d, min_periods=d).std(ddof=1)
    ref_z = ref_z.replace([np.inf, -np.inf], np.nan)
    eq_zscore = np.allclose(ts_zscore(s_x, d), ref_z, equal_nan=True)
    # ts_argmax
    ref_argmax = s_x.rolling(d, min_periods=d).apply(lambda w: float(np.argmax(w)) + 1.0, raw=True)
    eq_argmax = np.allclose(ts_argmax(s_x, d), ref_argmax, equal_nan=True)
    # ts_argmin
    ref_argmin = s_x.rolling(d, min_periods=d).apply(lambda w: float(np.argmin(w)) + 1.0, raw=True)
    eq_argmin = np.allclose(ts_argmin(s_x, d), ref_argmin, equal_nan=True)

    results["standard_equivalence"] = {
        "ts_mean": eq_mean,
        "ts_sum": eq_sum,
        "ts_max": eq_max,
        "ts_min": eq_min,
        "ts_rank": eq_rank,
        "ts_corr": eq_corr,
        "ts_zscore": eq_zscore,
        "ts_argmax": eq_argmax,
        "ts_argmin": eq_argmin,
    }

    # -------------------------------------------------------------
    # 2. Edge Case: Empty Series (N = 0)
    # -------------------------------------------------------------
    empty_s = pd.Series([], dtype=float)
    empty_arr = np.array([], dtype=float)
    
    empty_tests = {}
    for name, fn in [
        ("ts_mean", ts_mean), ("ts_sum", ts_sum), ("ts_max", ts_max), ("ts_min", ts_min),
        ("ts_rank", ts_rank), ("ts_zscore", ts_zscore), ("ts_argmax", ts_argmax), ("ts_argmin", ts_argmin)
    ]:
        res_s = fn(empty_s, 5)
        res_arr = fn(empty_arr, 5)
        ok = isinstance(res_s, pd.Series) and len(res_s) == 0 and isinstance(res_arr, np.ndarray) and len(res_arr) == 0
        empty_tests[name] = ok
    
    res_corr_s = ts_corr(empty_s, empty_s, 5)
    res_corr_arr = ts_corr(empty_arr, empty_arr, 5)
    empty_tests["ts_corr"] = isinstance(res_corr_s, pd.Series) and len(res_corr_s) == 0 and isinstance(res_corr_arr, np.ndarray) and len(res_corr_arr) == 0
    results["edge_empty_series"] = empty_tests

    # -------------------------------------------------------------
    # 3. Edge Case: Window d > len(x)
    # -------------------------------------------------------------
    short_s = pd.Series([10.0, 20.0, 30.0])
    short_arr = np.array([10.0, 20.0, 30.0])
    d_large = 5
    
    large_window_tests = {}
    for name, fn in [
        ("ts_mean", ts_mean), ("ts_sum", ts_sum), ("ts_max", ts_max), ("ts_min", ts_min),
        ("ts_rank", ts_rank), ("ts_zscore", ts_zscore), ("ts_argmax", ts_argmax), ("ts_argmin", ts_argmin)
    ]:
        res_s = fn(short_s, d_large)
        res_arr = fn(short_arr, d_large)
        ok = (isinstance(res_s, pd.Series) and len(res_s) == 3 and res_s.isna().all() and
              isinstance(res_arr, np.ndarray) and len(res_arr) == 3 and np.isnan(res_arr).all())
        large_window_tests[name] = ok
        
    res_corr_s = ts_corr(short_s, short_s, d_large)
    res_corr_arr = ts_corr(short_arr, short_arr, d_large)
    large_window_tests["ts_corr"] = (isinstance(res_corr_s, pd.Series) and len(res_corr_s) == 3 and res_corr_s.isna().all() and
                                    isinstance(res_corr_arr, np.ndarray) and len(res_corr_arr) == 3 and np.isnan(res_corr_arr).all())
    results["edge_window_larger_than_length"] = large_window_tests

    # -------------------------------------------------------------
    # 4. Edge Case: Window d = 1
    # -------------------------------------------------------------
    s_d1 = pd.Series([10.0, 25.0, 15.0, 40.0])
    d1_tests = {}
    
    d1_tests["ts_mean"] = np.allclose(ts_mean(s_d1, 1), s_d1)
    d1_tests["ts_sum"] = np.allclose(ts_sum(s_d1, 1), s_d1)
    d1_tests["ts_max"] = np.allclose(ts_max(s_d1, 1), s_d1)
    d1_tests["ts_min"] = np.allclose(ts_min(s_d1, 1), s_d1)
    d1_tests["ts_rank"] = np.allclose(ts_rank(s_d1, 1), np.ones(4))
    d1_tests["ts_corr"] = ts_corr(s_d1, s_d1, 1).isna().all()
    # ts_zscore for d=1 returns 0.0 (constant 0 vector for non-NaN elements)
    d1_tests["ts_zscore"] = np.allclose(ts_zscore(s_d1, 1), np.zeros(4))
    d1_tests["ts_argmax"] = np.allclose(ts_argmax(s_d1, 1), np.ones(4))
    d1_tests["ts_argmin"] = np.allclose(ts_argmin(s_d1, 1), np.ones(4))
    results["edge_window_d_1"] = d1_tests

    # -------------------------------------------------------------
    # 5. Edge Case: Constant Series with Zero Variance
    # -------------------------------------------------------------
    const_s1 = pd.Series([7.0, 7.0, 7.0, 7.0, 7.0])
    const_s2 = pd.Series([3.0, 3.0, 3.0, 3.0, 3.0])
    d_const = 3
    
    const_tests = {}
    const_tests["ts_mean"] = np.allclose(ts_mean(const_s1, d_const).iloc[2:], 7.0)
    const_tests["ts_sum"] = np.allclose(ts_sum(const_s1, d_const).iloc[2:], 21.0)
    const_tests["ts_max"] = np.allclose(ts_max(const_s1, d_const).iloc[2:], 7.0)
    const_tests["ts_min"] = np.allclose(ts_min(const_s1, d_const).iloc[2:], 7.0)
    # ts_rank for constant series of window 3: rank = (0 + 0.5*4)/3 = 2/3 = 0.6666667
    const_tests["ts_rank"] = np.allclose(ts_rank(const_s1, d_const).iloc[2:], 2.0 / 3.0)
    const_tests["ts_corr"] = ts_corr(const_s1, const_s2, d_const).iloc[2:].isna().all()
    const_tests["ts_zscore"] = np.allclose(ts_zscore(const_s1, d_const).iloc[2:], 0.0)
    const_tests["ts_argmax"] = np.allclose(ts_argmax(const_s1, d_const).iloc[2:], 1.0)
    const_tests["ts_argmin"] = np.allclose(ts_argmin(const_s1, d_const).iloc[2:], 1.0)
    results["edge_zero_variance"] = const_tests

    # -------------------------------------------------------------
    # 6. Edge Case: Series Containing NaNs
    # -------------------------------------------------------------
    nan_s = pd.Series([10.0, np.nan, 30.0, 40.0, 50.0, np.nan, 70.0])
    nan_s2 = pd.Series([5.0, 15.0, np.nan, 25.0, 35.0, 45.0, 55.0])
    d_nan = 3
    
    nan_tests = {}
    for name, fn in [
        ("ts_mean", ts_mean), ("ts_sum", ts_sum), ("ts_max", ts_max), ("ts_min", ts_min),
        ("ts_rank", ts_rank), ("ts_zscore", ts_zscore), ("ts_argmax", ts_argmax), ("ts_argmin", ts_argmin)
    ]:
        res = fn(nan_s, d_nan)
        # Windows containing NaN must yield NaN in output
        # Index 0,1: padding -> NaN
        # Index 2: window [10, NaN, 30] -> has NaN -> NaN
        # Index 3: window [NaN, 30, 40] -> has NaN -> NaN
        # Index 4: window [30, 40, 50] -> no NaN -> non-NaN
        # Index 5: window [40, 50, NaN] -> has NaN -> NaN
        # Index 6: window [50, NaN, 70] -> has NaN -> NaN
        expected_nan_mask = [True, True, True, True, False, True, True]
        nan_ok = (res.isna().to_numpy() == expected_nan_mask).all()
        nan_tests[name] = bool(nan_ok)
        
    res_corr_nan = ts_corr(nan_s, nan_s2, d_nan)
    corr_nan_ok = (res_corr_nan.isna().to_numpy() == [True, True, True, True, False, True, True]).all()
    nan_tests["ts_corr"] = bool(corr_nan_ok)
    results["edge_series_with_nans"] = nan_tests

    # -------------------------------------------------------------
    # 7. Invalid Parameter Validation
    # -------------------------------------------------------------
    invalid_tests = {}
    
    def check_raises(fn, *args):
        try:
            fn(*args)
            return False
        except ValueError:
            return True
            
    invalid_tests["d_zero"] = check_raises(ts_mean, s_x, 0)
    invalid_tests["d_negative"] = check_raises(ts_mean, s_x, -5)
    invalid_tests["d_float"] = check_raises(ts_mean, s_x, 3.5)
    invalid_tests["d_bool"] = check_raises(ts_mean, s_x, True)
    invalid_tests["2d_input"] = check_raises(ts_mean, np.ones((10, 5)), 3)
    invalid_tests["mismatched_corr_shape"] = check_raises(ts_corr, np.ones(10), np.ones(20), 3)
    results["invalid_parameter_handling"] = invalid_tests

    return results


if __name__ == "__main__":
    res = run_all_tests()
    print("RESULTS:")
    for category, category_res in res.items():
        print(f"\n--- {category} ---")
        for test_name, status in category_res.items():
            print(f"  {test_name:<30}: {'PASS' if status else 'FAIL'}")
