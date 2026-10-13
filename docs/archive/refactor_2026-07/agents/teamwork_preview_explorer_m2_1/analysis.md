# Analysis Report: AlphaPrimitives Module Interface & Architectural Design

**Module**: `core_engine/AlphaPrimitives.py`  
**Milestone**: Milestone 2 (Implement AlphaPrimitives & Benchmark)  
**Author**: Explorer 1  
**Date**: 2026-07-21  

---

## 1. Architectural Overview & Design Goals

The primary objective of `core_engine/AlphaPrimitives.py` is to establish a high-performance, fully vectorized time-series primitives module for the `alpha_farm` strategy discovery engine. Legacy strategy generation relied on heavy Pandas `.rolling().apply()` calls or restricted sandbox abstractions, creating computational bottlenecks during MCTS strategy search.

`AlphaPrimitives.py` provides clean NumPy-backed time-series operators operating directly on contiguous memory via NumPy strided sliding window views (`np.lib.stride_tricks.sliding_window_view`).

### Key Design Goals:
1. **Mathematical Equivalence**: Match Pandas standard `.rolling(d)` calculations within single/double floating-point precision ($10^{-6}$).
2. **High-Performance Vectorization**: Eliminate Python-level loops and `.apply()` overhead.
3. **Seamless Type Compatibility**: Accept both `pd.Series` and `np.ndarray` inputs smoothly. Preserve index, series name, and type metadata when input is `pd.Series`.
4. **Strict Length & NaN Padding Rules**: Ensure output array length $N$ equals input array length $N$, with exact leading $d-1$ `np.nan` padding for initial periods.

---

## 2. Module Interface & Type Preservation Specification

### 2.1 Supported Input/Output Types
All primitive functions accept inputs of type `Union[pd.Series, np.ndarray]`.

- **If input is `pd.Series`**:
  - Output is `pd.Series`.
  - Output `index` is identical to input `x.index`.
  - Output `name` is identical to input `x.name`.
- **If input is `np.ndarray`**:
  - Output is `np.ndarray` (1D array of `dtype=np.float64`).
- **If input is 2-series operation (`ts_corr(x, y, d)`)**:
  - If `x` is `pd.Series`, output is `pd.Series` with `x.index` and `x.name`.
  - `x` and `y` must have equal length $N$; otherwise, raise `ValueError`.

### 2.2 Standard Decorator / Wrapper Architecture
To avoid duplicated type-checking, array unwrapping, and output re-wrapping across primitives, `AlphaPrimitives.py` utilizes a decorator pattern:

```python
from functools import wraps
from typing import Union, Tuple, Optional, Callable
import numpy as np
import pandas as pd

ArrayOrSeries = Union[pd.Series, np.ndarray]

def ts_primitive(func: Callable) -> Callable:
    """
    Decorator that standardizes window validation, type conversion, 
    pandas index preservation, and d-1 NaN padding across single-series primitives.
    """
    @wraps(func)
    def wrapper(x: ArrayOrSeries, d: int, *args, **kwargs) -> ArrayOrSeries:
        if not isinstance(d, int) or d < 1:
            raise ValueError(f"Window size d must be a positive integer >= 1, got {d}")
        
        is_series = isinstance(x, pd.Series)
        index = x.index if is_series else None
        name = x.name if is_series else None
        
        arr = x.values if is_series else np.asarray(x)
        if arr.ndim != 1:
            raise ValueError(f"Input array/series must be 1D, got shape {arr.shape}")
            
        N = len(arr)
        if N == 0:
            res = np.array([], dtype=np.float64)
            return pd.Series(res, index=index, name=name) if is_series else res
            
        if d > N:
            res = np.full(N, np.nan, dtype=np.float64)
            return pd.Series(res, index=index, name=name) if is_series else res
            
        arr_float = arr.astype(np.float64)
        windows = np.lib.stride_tricks.sliding_window_view(arr_float, window_shape=d)
        
        kernel_res = func(windows, *args, **kwargs)
        
        out = np.full(N, np.nan, dtype=np.float64)
        out[d - 1 :] = kernel_res
        
        if is_series:
            return pd.Series(out, index=index, name=name)
        return out
        
    return wrapper
```

---

## 3. NaN Padding Rules & Length Protocol

For any input series of length $N$ and rolling window $d$:

1. **Length Invariant**: $\text{len}(\text{output}) == N$.
2. **Leading Padding**: For $i \in [0, d-2]$, $\text{output}[i] = \text{np.nan}$.
3. **Valid Range**: For $i \in [d-1, N-1]$, $\text{output}[i]$ is computed over the window slice $x[i - d + 1 : i + 1]$.
4. **Boundary Condition ($d > N$)**: If window size $d$ exceeds total length $N$, all $N$ elements of output are populated with `np.nan`.
5. **Internal NaN Propagation**: If any value within window $x[i - d + 1 : i + 1]$ is `np.nan`, the resulting calculation for index $i$ evaluates to `np.nan` (matching standard Pandas `.rolling(d, min_periods=d)` behavior).

---

## 4. Mathematical Specifications & Primitive Function Signatures

### 1. `ts_mean(x, d)`
- **Signature**: `ts_mean(x: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: Moving arithmetic mean over window $d$.
- **Formula**:
  $$\text{ts\_mean}(x, d)[i] = \frac{1}{d} \sum_{k=0}^{d-1} x[i - k]$$
- **Kernel Implementation**:
  ```python
  @ts_primitive
  def ts_mean_kernel(windows: np.ndarray) -> np.ndarray:
      return np.mean(windows, axis=1)
  ```

### 2. `ts_sum(x, d)`
- **Signature**: `ts_sum(x: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: Moving summation over window $d$.
- **Formula**:
  $$\text{ts\_sum}(x, d)[i] = \sum_{k=0}^{d-1} x[i - k]$$
- **Kernel Implementation**:
  ```python
  @ts_primitive
  def ts_sum_kernel(windows: np.ndarray) -> np.ndarray:
      return np.sum(windows, axis=1)
  ```

### 3. `ts_max(x, d)`
- **Signature**: `ts_max(x: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: Moving maximum over window $d$.
- **Formula**:
  $$\text{ts\_max}(x, d)[i] = \max_{0 \le k \le d-1} x[i - k]$$
- **Kernel Implementation**:
  ```python
  @ts_primitive
  def ts_max_kernel(windows: np.ndarray) -> np.ndarray:
      return np.max(windows, axis=1)
  ```

### 4. `ts_min(x, d)`
- **Signature**: `ts_min(x: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: Moving minimum over window $d$.
- **Formula**:
  $$\text{ts\_min}(x, d)[i] = \min_{0 \le k \le d-1} x[i - k]$$
- **Kernel Implementation**:
  ```python
  @ts_primitive
  def ts_min_kernel(windows: np.ndarray) -> np.ndarray:
      return np.min(windows, axis=1)
  ```

### 5. `ts_rank(x, d)`
- **Signature**: `ts_rank(x: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: Moving percentile rank of current bar $x[i]$ within window $d$.
- **Convention & Tie Handling**:
  Returns the relative percentile rank of the current element $x[i]$ within the $d$-bar window, normalized to range $[0.0, 1.0]$. Matches Pandas `pd.Series(window).rank(pct=True).iloc[-1]` using average rank for ties.
- **Formula**:
  $$\text{rank}(x[i]) = (\text{count}(x[k] < x[i]) + 1.0) + \frac{\text{count}(x[k] == x[i]) - 1}{2.0}$$
  $$\text{ts\_rank}(x, d)[i] = \frac{\text{rank}(x[i])}{d}$$
- **Kernel Implementation**:
  ```python
  @ts_primitive
  def ts_rank_kernel(windows: np.ndarray) -> np.ndarray:
      nan_mask = np.isnan(windows).any(axis=1)
      curr = windows[:, -1:]  # Current bar values (shape: M x 1)
      
      less = (windows < curr).sum(axis=1)
      equal = (windows == curr).sum(axis=1)
      
      rank = (less + 1.0) + (equal - 1.0) / 2.0
      pct_rank = rank / windows.shape[1]
      pct_rank[nan_mask] = np.nan
      return pct_rank
  ```

### 6. `ts_corr(x, y, d)`
- **Signature**: `ts_corr(x: ArrayOrSeries, y: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: Moving Pearson correlation coefficient between $x$ and $y$ over window $d$.
- **Formula**:
  $$r_{x,y} = \frac{\sum (x_k - \bar{x})(y_k - \bar{y})}{\sqrt{\sum (x_k - \bar{x})^2 \sum (y_k - \bar{y})^2}}$$
- **Zero Variance & Numerical Stability**:
  If either variance is zero (or $< 10^{-12}$), return `np.nan`. Clip output to $[-1.0, 1.0]$ to guard against float precision overshooting.
- **Implementation**:
  ```python
  def ts_corr(x: ArrayOrSeries, y: ArrayOrSeries, d: int) -> ArrayOrSeries:
      if not isinstance(d, int) or d < 1:
          raise ValueError(f"Window size d must be positive integer >= 1, got {d}")
      
      is_series = isinstance(x, pd.Series)
      index = x.index if is_series else None
      name = x.name if is_series else None
      
      arr_x = x.values if is_series else np.asarray(x)
      arr_y = y.values if isinstance(y, pd.Series) else np.asarray(y)
      
      if arr_x.shape != arr_y.shape:
          raise ValueError(f"Input shapes must match, got {arr_x.shape} and {arr_y.shape}")
      if arr_x.ndim != 1:
          raise ValueError(f"Input must be 1D, got shape {arr_x.shape}")
          
      N = len(arr_x)
      if N == 0:
          res = np.array([], dtype=np.float64)
          return pd.Series(res, index=index, name=name) if is_series else res
          
      if d > N:
          res = np.full(N, np.nan, dtype=np.float64)
          return pd.Series(res, index=index, name=name) if is_series else res

      win_x = np.lib.stride_tricks.sliding_window_view(arr_x.astype(np.float64), d)
      win_y = np.lib.stride_tricks.sliding_window_view(arr_y.astype(np.float64), d)
      
      nan_mask = np.isnan(win_x).any(axis=1) | np.isnan(win_y).any(axis=1)
      
      mean_x = np.mean(win_x, axis=1, keepdims=True)
      mean_y = np.mean(win_y, axis=1, keepdims=True)
      
      dx = win_x - mean_x
      dy = win_y - mean_y
      
      cov = np.sum(dx * dy, axis=1)
      var_x = np.sum(dx ** 2, axis=1)
      var_y = np.sum(dy ** 2, axis=1)
      
      denom = np.sqrt(var_x * var_y)
      
      with np.errstate(divide='ignore', invalid='ignore'):
          corr = np.where(denom > 1e-12, cov / denom, np.nan)
          corr = np.clip(corr, -1.0, 1.0)
          corr[nan_mask] = np.nan
          
      out = np.full(N, np.nan, dtype=np.float64)
      out[d - 1 :] = corr
      
      if is_series:
          return pd.Series(out, index=index, name=name)
      return out
  ```

### 7. `ts_zscore(x, d)`
- **Signature**: `ts_zscore(x: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: Moving Z-score of current bar $x[i]$ within window $d$.
- **Formula**:
  $$\text{ts\_zscore}(x, d)[i] = \frac{x[i] - \mu_d}{\sigma_d}$$
  where $\sigma_d$ is sample standard deviation ($\text{ddof}=1$).
- **Zero Variance Handling**:
  If $\sigma_d < 10^{-12}$, return `0.0` (or `np.nan` if standard deviation is undefined).
- **Kernel Implementation**:
  ```python
  @ts_primitive
  def ts_zscore_kernel(windows: np.ndarray) -> np.ndarray:
      means = np.mean(windows, axis=1)
      stds = np.std(windows, axis=1, ddof=1)
      curr = windows[:, -1]
      
      with np.errstate(divide='ignore', invalid='ignore'):
          zscore = np.where(stds > 1e-12, (curr - means) / stds, 0.0)
          
      nan_mask = np.isnan(windows).any(axis=1)
      zscore[nan_mask] = np.nan
      return zscore
  ```

### 8. `ts_argmax(x, d)`
- **Signature**: `ts_argmax(x: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: 1-based relative index position of the maximum value within rolling window $[1, d]$.
- **Indexing Convention**:
  - `1.0` = oldest element in window ($x[i - d + 1]$).
  - `d` = newest/current element in window ($x[i]$).
- **Kernel Implementation**:
  ```python
  @ts_primitive
  def ts_argmax_kernel(windows: np.ndarray) -> np.ndarray:
      nan_mask = np.isnan(windows).any(axis=1)
      idx = np.argmax(windows, axis=1).astype(np.float64) + 1.0
      idx[nan_mask] = np.nan
      return idx
  ```

### 9. `ts_argmin(x, d)`
- **Signature**: `ts_argmin(x: ArrayOrSeries, d: int) -> ArrayOrSeries`
- **Description**: 1-based relative index position of the minimum value within rolling window $[1, d]$.
- **Indexing Convention**:
  - `1.0` = oldest element in window ($x[i - d + 1]$).
  - `d` = newest/current element in window ($x[i]$).
- **Kernel Implementation**:
  ```python
  @ts_primitive
  def ts_argmin_kernel(windows: np.ndarray) -> np.ndarray:
      nan_mask = np.isnan(windows).any(axis=1)
      idx = np.argmin(windows, axis=1).astype(np.float64) + 1.0
      idx[nan_mask] = np.nan
      return idx
  ```

---

## 5. Edge Case Matrix & Input Validation Rules

| Scenario | Condition | Expected Behavior |
|---|---|---|
| Invalid Window | `d <= 0` or non-int | Raise `ValueError("Window size d must be a positive integer >= 1")` |
| Window Exceeds Length | `d > N` | Return array of length $N$ filled with `np.nan` |
| Empty Input | `N == 0` | Return empty array/series |
| Dimension Mismatch | `x.shape != y.shape` in `ts_corr` | Raise `ValueError("Input series x and y must have matching shapes")` |
| Non-1D Input | `x.ndim != 1` | Raise `ValueError("Input array/series must be 1D")` |
| Existing NaNs in Window | Window slice has `np.nan` | Output element evaluates to `np.nan` |
| Zero Variance | Flat/constant window | `ts_zscore` returns `0.0`, `ts_corr` returns `np.nan` |
| Index Preservation | Input is `pd.Series` | Output is `pd.Series` with exact matching index and name |

---

## 6. Verification & Test Strategy for Implementer

To verify correctness and benchmark performance in Milestone 2:

1. **Mathematical Equivalence Test**:
   - Compare each function output against Pandas baseline (`pd.Series.rolling(d)`).
   - `np.testing.assert_allclose(actual, pandas_expected, rtol=1e-6, equal_nan=True)`.
2. **Type & Index Preservation Test**:
   - Test passing `pd.Series` with DatetimeIndex and custom name. Verify return type is `pd.Series`, name is preserved, index matches.
   - Test passing `np.ndarray`. Verify return type is `np.ndarray`.
3. **Leading NaN Count Test**:
   - For $N=1000, d=20$, verify indices $0..18$ are `np.nan` and index $19$ is non-nan. Total length must be 1000.
4. **Performance Benchmark**:
   - Run `benchmark_primitives.py` comparing runtime over 100,000 rows across $d \in [5, 20, 60, 120]$. Expect $\ge 5\times$ to $20\times$ speedup over Pandas `.rolling().apply()`.

---
