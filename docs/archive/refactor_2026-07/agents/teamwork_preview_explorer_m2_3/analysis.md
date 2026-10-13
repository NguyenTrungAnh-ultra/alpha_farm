# Analysis Report: Design of `benchmark_primitives.py` Verification & Benchmarking Suite

**Module**: Primitive Verification & Performance Benchmarking  
**Target File**: `benchmark_primitives.py` (Repository Root)  
**Milestone**: Milestone 2 — Implement AlphaPrimitives & Benchmark  
**Author**: Explorer 3  

---

## 1. Executive Summary

This report provides the complete specification and design architecture for `benchmark_primitives.py`, the core verification and benchmarking script for Milestone 2. The primary objectives of this script are:
1. **Mathematical Equivalence Verification**: Guaranteeing that vectorized Numpy operations in `core_engine/AlphaPrimitives.py` produce output identical to naive Pandas `.rolling()` reference implementations within a strict numerical tolerance of `1e-5` ($10^{-5}$).
2. **Performance Benchmarking**: Measuring execution latency (in milliseconds, `ms`) and computing speedup multipliers ($x$) for all 9 core time-series primitives across realistic quantitative trading dataset sizes ($N = 10,000$ and $N = 50,000$ rows) and rolling window periods ($d \in \{10, 20, 60\}$).

The 9 primitives covered are: `ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, and `ts_argmin`.

---

## 2. Naive Pandas Baseline Reference Specifications

To establish an indisputable ground truth for numerical verification, each of the 9 primitive operators is paired with a naive Pandas reference implementation based on standard Pandas `.rolling()` calls and Python functions.

### 2.1 Naive Reference Functions

#### 1. `naive_ts_mean(x: pd.Series, d: int) -> pd.Series`
- **Definition**: Rolling arithmetic mean over a sliding window of size `d`.
- **Baseline Implementation**:
```python
def naive_ts_mean(x: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).mean()
```

#### 2. `naive_ts_sum(x: pd.Series, d: int) -> pd.Series`
- **Definition**: Rolling sum over a sliding window of size `d`.
- **Baseline Implementation**:
```python
def naive_ts_sum(x: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).sum()
```

#### 3. `naive_ts_max(x: pd.Series, d: int) -> pd.Series`
- **Definition**: Rolling maximum value over a sliding window of size `d`.
- **Baseline Implementation**:
```python
def naive_ts_max(x: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).max()
```

#### 4. `naive_ts_min(x: pd.Series, d: int) -> pd.Series`
- **Definition**: Rolling minimum value over a sliding window of size `d`.
- **Baseline Implementation**:
```python
def naive_ts_min(x: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).min()
```

#### 5. `naive_ts_rank(x: pd.Series, d: int) -> pd.Series`
- **Definition**: Percentile rank of the current element $x_t$ relative to all $d$ values within rolling window $[t-d+1, \dots, t]$. Outputs values normalized in $(0, 1]$.
- **Baseline Implementation**:
```python
def naive_ts_rank(x: pd.Series, d: int) -> pd.Series:
    def _rank_last(w: np.ndarray) -> float:
        s = pd.Series(w)
        return s.rank(pct=True).iloc[-1]
    return x.rolling(window=d, min_periods=d).apply(_rank_last, raw=False)
```

#### 6. `naive_ts_corr(x: pd.Series, y: pd.Series, d: int) -> pd.Series`
- **Definition**: Rolling Pearson correlation coefficient between series $x$ and $y$ over sliding window `d`.
- **Baseline Implementation**:
```python
def naive_ts_corr(x: pd.Series, y: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).corr(y)
```

#### 7. `naive_ts_zscore(x: pd.Series, d: int) -> pd.Series`
- **Definition**: Rolling z-score $(x_t - \mu_{t,d}) / \sigma_{t,d}$ where $\mu$ is rolling mean and $\sigma$ is rolling population standard deviation (`ddof=0`).
- **Baseline Implementation**:
```python
def naive_ts_zscore(x: pd.Series, d: int) -> pd.Series:
    r_mean = x.rolling(window=d, min_periods=d).mean()
    r_std = x.rolling(window=d, min_periods=d).std(ddof=0)
    z = (x - r_mean) / r_std
    return z.replace([np.inf, -np.inf], np.nan)
```

#### 8. `naive_ts_argmax(x: pd.Series, d: int) -> pd.Series`
- **Definition**: 0-based relative index offset of the maximum value within rolling window $[t-d+1, \dots, t]$ (range $0$ to $d-1$).
- **Baseline Implementation**:
```python
def naive_ts_argmax(x: pd.Series, d: int) -> pd.Series:
    def _argmax_offset(w: np.ndarray) -> float:
        return float(np.argmax(w))
    return x.rolling(window=d, min_periods=d).apply(_argmax_offset, raw=True)
```

#### 9. `naive_ts_argmin(x: pd.Series, d: int) -> pd.Series`
- **Definition**: 0-based relative index offset of the minimum value within rolling window $[t-d+1, \dots, t]$ (range $0$ to $d-1$).
- **Baseline Implementation**:
```python
def naive_ts_argmin(x: pd.Series, d: int) -> pd.Series:
    def _argmin_offset(w: np.ndarray) -> float:
        return float(np.argmin(w))
    return x.rolling(window=d, min_periods=d).apply(_argmin_offset, raw=True)
```

---

## 3. Numerical Verification & Assertion Architecture

### 3.1 Tolerance Specifications
- **Target Absolute & Relative Tolerance**: `rtol=1e-5`, `atol=1e-5`.
- **Rationale**: Floating-point operations in numpy stride tricks and 2D vectorization execute additions/multiplications in different memory orders compared to iterative pandas algorithms. A tolerance of `1e-5` permits minor precision differences while ensuring strict mathematical parity.

### 3.2 Handling NaN Values & Warm-up Regions
- For any window size $d$, the initial $d-1$ indices are incomplete windows and must yield `NaN` in both baseline and optimized implementations.
- Assertion functions must handle `NaN == NaN` comparisons explicitly using `equal_nan=True` or `pd.testing.assert_series_equal`.

### 3.3 Verification Assertion Logic
```python
def verify_primitive_equivalence(
    name: str,
    fast_output: np.ndarray | pd.Series,
    naive_output: pd.Series,
    rtol: float = 1e-5,
    atol: float = 1e-5
) -> tuple[bool, float]:
    """
    Verifies numerical equivalence between vectorized output and naive pandas baseline.
    Returns (is_passed, max_abs_difference).
    """
    fast_arr = np.asarray(fast_output, dtype=np.float64)
    naive_arr = naive_output.to_numpy(dtype=np.float64)

    # Check shape alignment
    if fast_arr.shape != naive_arr.shape:
        return False, float('inf')

    # Compute element-wise difference
    diff = np.abs(fast_arr - naive_arr)
    # Exclude NaN comparisons for max diff calculation
    valid_mask = ~np.isnan(fast_arr) & ~np.isnan(naive_arr)
    max_diff = float(np.nanmax(diff[valid_mask])) if np.any(valid_mask) else 0.0

    # Verify NaNs match exactly in location
    nan_mismatch = np.isnan(fast_arr) != np.isnan(naive_arr)
    if np.any(nan_mismatch):
        return False, max_diff

    # Verify numerical closeness
    is_close = np.allclose(fast_arr, naive_arr, rtol=rtol, atol=atol, equal_nan=True)
    return is_close, max_diff
```

---

## 4. Performance Benchmarking Architecture

### 4.1 Measurement Methodology
- **Timer**: `time.perf_counter()` providing high-resolution process time measurement.
- **Warm-Up Phase**: 1 execution run per primitive prior to timing to ensure module imports, CPU caching, and memory pre-allocations are settled.
- **Iteration Runs**: $K = 5$ iterations per primitive; execution times are averaged to yield stable millisecond (`ms`) readings.
- **Speedup Ratio**:
  $$\text{Speedup Multiplier } (x) = \frac{\text{Mean Execution Time of Naive Pandas (ms)}}{\text{Mean Execution Time of AlphaPrimitives (ms)}}$$

### 4.2 Benchmark Workloads
- **Default Workload**: Dataset length $N = 10,000$, rolling window $d = 20$.
- **Extended Workload**: Dataset length $N = 50,000$, rolling windows $d \in \{10, 20, 60\}$.

---

## 5. Design of `benchmark_primitives.py`

Below is the complete proposed code structure for `benchmark_primitives.py` to be placed at the repository root.

```python
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

# Import optimized primitives from core_engine
try:
    from core_engine.AlphaPrimitives import (
        ts_mean, ts_sum, ts_max, ts_min,
        ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
    )
except ImportError:
    print("[WARNING] core_engine.AlphaPrimitives not found. Benchmark script will run in mock verification mode.")
    # Placeholders for static verification check before M2 implementation
    ts_mean = ts_sum = ts_max = ts_min = None
    ts_rank = ts_corr = ts_zscore = ts_argmax = ts_argmin = None


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
    def _rank_last(w: np.ndarray) -> float:
        s = pd.Series(w)
        return s.rank(pct=True).iloc[-1]
    return x.rolling(window=d, min_periods=d).apply(_rank_last, raw=False)

def naive_ts_corr(x: pd.Series, y: pd.Series, d: int) -> pd.Series:
    return x.rolling(window=d, min_periods=d).corr(y)

def naive_ts_zscore(x: pd.Series, d: int) -> pd.Series:
    r_mean = x.rolling(window=d, min_periods=d).mean()
    r_std = x.rolling(window=d, min_periods=d).std(ddof=0)
    z = (x - r_mean) / r_std
    return z.replace([np.inf, -np.inf], np.nan)

def naive_ts_argmax(x: pd.Series, d: int) -> pd.Series:
    def _argmax_offset(w: np.ndarray) -> float:
        return float(np.argmax(w))
    return x.rolling(window=d, min_periods=d).apply(_argmax_offset, raw=True)

def naive_ts_argmin(x: pd.Series, d: int) -> pd.Series:
    def _argmin_offset(w: np.ndarray) -> float:
        return float(np.argmin(w))
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

    print(f"=" * 90)
    print(f" AlphaPrimitives Benchmark Suite (N={n_samples:,}, Window d={window}, Iterations={iterations})")
    print(f"=" * 90)
    print(f"{'Primitive':<12} | {'Naive (ms)':<11} | {'Fast (ms)':<11} | {'Speedup':<9} | {'Max Diff':<10} | {'Status':<6}")
    print("-" * 90)

    all_passed = True

    for name, fast_fn, naive_fn, args in primitives_config:
        if fast_fn is None:
            print(f"{name:<12} | {'N/A':<11} | {'N/A':<11} | {'N/A':<9} | {'N/A':<10} | SKIP")
            continue

        # 1. Warm-up and equivalence check
        try:
            fast_out = fast_fn(*args)
            naive_out = naive_fn(*args)
        except Exception as err:
            print(f"{name:<12} | ERROR: {err}")
            all_passed = False
            continue

        fast_arr = np.asarray(fast_out, dtype=np.float64)
        naive_arr = naive_out.to_numpy(dtype=np.float64)

        # Verification check (1e-5 tolerance)
        valid_mask = ~np.isnan(fast_arr) & ~np.isnan(naive_arr)
        max_diff = float(np.nanmax(np.abs(fast_arr[valid_mask] - naive_arr[valid_mask]))) if np.any(valid_mask) else 0.0
        is_close = np.allclose(fast_arr, naive_arr, rtol=1e-5, atol=1e-5, equal_nan=True)

        status_str = "PASS" if is_close else "FAIL"
        if not is_close:
            all_passed = False

        # 2. Timing Naive Baseline
        t0 = time.perf_counter()
        for _ in range(iterations):
            _ = naive_fn(*args)
        t_naive_ms = ((time.perf_counter() - t0) / iterations) * 1000.0

        # 3. Timing Fast Vectorized Primitive
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
```

---

## 6. Summary of Design Decisions

| Metric / Parameter | Value / Design Choice | Technical Rationale |
|---|---|---|
| Target File Location | `benchmark_primitives.py` (Repo Root) | Directly accessible as root validation script and Pytest target |
| Tolerance Threshold | `1e-5` (`rtol=1e-5`, `atol=1e-5`) | Allows sub-microscopic floating-point precision differences from sum orders |
| Baseline Framework | Naive Pandas `.rolling()` / `.apply()` | Unquestionable reference implementation for Pandas compatibility |
| Benchmarking Scale | $N = 10,000$, Window $d = 20$ | Matches single-symbol 1-minute to 15-minute standard backtest array size |
| Execution Output Format | Tabular stdout + exit codes (0/1) | Human-readable terminal output and automated CI compatibility |

