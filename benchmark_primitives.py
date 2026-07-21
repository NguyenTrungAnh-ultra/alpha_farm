"""
benchmark_primitives.py
Repository Root Verification & Performance Benchmarking Script for AlphaPrimitives.

Usage:
    python benchmark_primitives.py [--size N] [--window D] [--iterations K]
"""

import sys
import time
import argparse
import numpy as np
import pandas as pd

from core_engine.AlphaPrimitives import (
    ts_mean, ts_sum, ts_max, ts_min,
    ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
)


# Naive Pandas Baseline References
def naive_ts_mean(x: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).mean()


def naive_ts_sum(x: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).sum()


def naive_ts_max(x: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).max()


def naive_ts_min(x: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).min()


def naive_ts_rank(x: pd.Series, d: int) -> pd.Series:
    def _rank_last(w: pd.Series) -> float:
        return float(w.rank(pct=True).iloc[-1])
    return x.rolling(window=d, min_periods=d).apply(_rank_last, raw=False)


def naive_ts_corr(x: pd.Series, y: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).corr(y)


def naive_ts_zscore(x: pd.Series, d: int) -> pd.Series:
    r_mean = x.rolling(window=d, min_periods=d).mean()
    r_std = x.rolling(window=d, min_periods=d).std(ddof=1)
    z = (x - r_mean) / r_std
    return z.replace([np.inf, -np.inf], np.nan)


def naive_ts_argmax(x: pd.Series, d: int) -> pd.Series:
    def _argmax_offset(w: np.ndarray) -> float:
        return float(np.argmax(w)) + 1.0
    return x.rolling(window=d, min_periods=d).apply(_argmax_offset, raw=True)


def naive_ts_argmin(x: pd.Series, d: int) -> pd.Series:
    def _argmin_offset(w: np.ndarray) -> float:
        return float(np.argmin(w)) + 1.0
    return x.rolling(window=d, min_periods=d).apply(_argmin_offset, raw=True)


def generate_benchmark_data(n_samples: int = 10000, seed: int = 42) -> tuple[pd.Series, pd.Series]:
    """Generates synthetic time series price data for benchmark tests."""
    np.random.seed(seed)
    returns_x = np.random.normal(0.0001, 0.01, size=n_samples)
    returns_y = np.random.normal(0.0001, 0.01, size=n_samples)
    
    price_x = pd.Series(100.0 * np.exp(np.cumsum(returns_x)), name="x")
    price_y = pd.Series(50.0 * np.exp(np.cumsum(returns_y)), name="y")
    return price_x, price_y


def run_benchmark_suite(n_samples: int = 10000, window: int = 20, iterations: int = 5) -> bool:
    """Runs equivalence assertions and execution timing for all 9 primitives."""
    x, y = generate_benchmark_data(n_samples=n_samples)

    primitives_config = [
        ("ts_mean", ts_mean, naive_ts_mean, (x, window)),
        ("ts_sum", ts_sum, naive_ts_sum, (x, window)),
        ("ts_max", ts_max, naive_ts_max, (x, window)),
        ("ts_min", ts_min, naive_ts_min, (x, window)),
        ("ts_rank", ts_rank, naive_ts_rank, (x, window)),
        ("ts_corr", ts_corr, naive_ts_corr, (x, y, window)),
        ("ts_zscore", ts_zscore, naive_ts_zscore, (x, window)),
        ("ts_argmax", ts_argmax, naive_ts_argmax, (x, window)),
        ("ts_argmin", ts_argmin, naive_ts_argmin, (x, window)),
    ]

    print("=" * 90)
    print(f" AlphaPrimitives Benchmark Suite (N={n_samples:,}, Window d={window}, Iterations={iterations})")
    print("=" * 90)
    print(f"{'Primitive':<12} | {'Naive (ms)':<11} | {'Fast (ms)':<11} | {'Speedup':<9} | {'Max Diff':<10} | {'Status':<6}")
    print("-" * 90)

    all_passed = True

    for name, fast_fn, naive_fn, args in primitives_config:
        try:
            fast_out = fast_fn(*args)
            naive_out = naive_fn(*args)
        except Exception as err:
            print(f"{name:<12} | ERROR: {err}")
            all_passed = False
            continue

        fast_arr = np.asarray(fast_out, dtype=np.float64)
        naive_arr = naive_out.to_numpy(dtype=np.float64)

        # Equivalence verification check (1e-5 tolerance)
        valid_mask = ~np.isnan(fast_arr) & ~np.isnan(naive_arr)
        max_diff = float(np.nanmax(np.abs(fast_arr[valid_mask] - naive_arr[valid_mask]))) if np.any(valid_mask) else 0.0
        is_close = np.allclose(fast_arr, naive_arr, rtol=1e-5, atol=1e-5, equal_nan=True)

        status_str = "PASS" if is_close else "FAIL"
        if not is_close:
            all_passed = False

        # Timing Naive Baseline
        t0 = time.perf_counter()
        for _ in range(iterations):
            _ = naive_fn(*args)
        t_naive_ms = ((time.perf_counter() - t0) / iterations) * 1000.0

        # Timing Fast Vectorized Primitive
        t0 = time.perf_counter()
        for _ in range(iterations):
            _ = fast_fn(*args)
        t_fast_ms = ((time.perf_counter() - t0) / iterations) * 1000.0

        speedup = t_naive_ms / t_fast_ms if t_fast_ms > 0 else 0.0

        print(f"{name:<12} | {t_naive_ms:>9.2f} ms | {t_fast_ms:>9.2f} ms | {speedup:>7.1f}x | {max_diff:>9.2e} | {status_str:<6}")

    print("=" * 90)
    if all_passed:
        print(" SUCCESS: All active primitive assertions verified within 1e-5 tolerance!")
    else:
        print(" FAILURE: One or more primitive assertions failed equivalence verification.")
    print("=" * 90)

    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AlphaPrimitives Verification & Benchmark Suite")
    parser.add_argument("--size", type=int, default=10000, help="Number of rows in synthetic time series")
    parser.add_argument("--window", type=int, default=20, help="Rolling window size d")
    parser.add_argument("--iterations", type=int, default=5, help="Number of timing iterations")
    args = parser.parse_args()

    success = run_benchmark_suite(n_samples=args.size, window=args.window, iterations=args.iterations)
    sys.exit(0 if success else 1)
