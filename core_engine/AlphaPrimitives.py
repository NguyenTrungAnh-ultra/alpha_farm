"""
core_engine/AlphaPrimitives.py

High-performance, fully vectorized time-series primitive operations for strategy discovery.
Replaces slow Pandas rolling loops with 2D NumPy strided window views.
"""

from functools import wraps
from typing import Union, Callable
import numpy as np
import pandas as pd

ArrayOrSeries = Union[pd.Series, np.ndarray]


def ts_primitive(func: Callable) -> Callable:
    """
    Decorator standardizing window size validation, input type handling,
    pandas index/name preservation, strided view creation, and leading (d-1) NaN padding.
    """
    @wraps(func)
    def wrapper(x: ArrayOrSeries, d: int, *args, **kwargs) -> ArrayOrSeries:
        if not isinstance(d, int) or isinstance(d, bool) or d < 1:
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


@ts_primitive
def ts_mean(windows: np.ndarray) -> np.ndarray:
    """Moving arithmetic mean over rolling window d."""
    return np.mean(windows, axis=1)


@ts_primitive
def ts_sum(windows: np.ndarray) -> np.ndarray:
    """Moving summation over rolling window d."""
    return np.sum(windows, axis=1)


@ts_primitive
def ts_max(windows: np.ndarray) -> np.ndarray:
    """Moving maximum over rolling window d."""
    return np.max(windows, axis=1)


@ts_primitive
def ts_min(windows: np.ndarray) -> np.ndarray:
    """Moving minimum over rolling window d."""
    return np.min(windows, axis=1)


@ts_primitive
def ts_rank(windows: np.ndarray) -> np.ndarray:
    """Moving percentile rank of current bar within rolling window d."""
    nan_mask = np.isnan(windows).any(axis=1)
    curr = windows[:, -1:]  # Shape (M, 1) for 2D broadcasting
    less = (windows < curr).sum(axis=1).astype(np.float64)
    equal = (windows == curr).sum(axis=1).astype(np.float64)
    rank = less + 0.5 * (equal + 1.0)
    pct_rank = rank / float(windows.shape[1])
    pct_rank[nan_mask] = np.nan
    return pct_rank


def ts_corr(x: ArrayOrSeries, y: ArrayOrSeries, d: int) -> ArrayOrSeries:
    """Moving Pearson correlation coefficient between x and y over rolling window d."""
    if not isinstance(d, int) or isinstance(d, bool) or d < 1:
        raise ValueError(f"Window size d must be a positive integer >= 1, got {d}")
    
    is_series = isinstance(x, pd.Series)
    index = x.index if is_series else None
    name = x.name if is_series else None
    
    arr_x = x.values if is_series else np.asarray(x)
    arr_y = y.values if isinstance(y, pd.Series) else np.asarray(y)
    
    if arr_x.shape != arr_y.shape:
        raise ValueError(f"Input shapes must match, got {arr_x.shape} and {arr_y.shape}")
    if arr_x.ndim != 1:
        raise ValueError(f"Input array/series must be 1D, got shape {arr_x.shape}")
        
    N = len(arr_x)
    if N == 0:
        res = np.array([], dtype=np.float64)
        return pd.Series(res, index=index, name=name) if is_series else res
        
    if d > N:
        res = np.full(N, np.nan, dtype=np.float64)
        return pd.Series(res, index=index, name=name) if is_series else res

    win_x = np.lib.stride_tricks.sliding_window_view(arr_x.astype(np.float64), window_shape=d)
    win_y = np.lib.stride_tricks.sliding_window_view(arr_y.astype(np.float64), window_shape=d)
    
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


@ts_primitive
def ts_zscore(windows: np.ndarray) -> np.ndarray:
    """Moving Z-score of current bar within rolling window d."""
    nan_mask = np.isnan(windows).any(axis=1)
    means = np.mean(windows, axis=1)
    stds = np.std(windows, axis=1, ddof=1)
    curr = windows[:, -1]
    
    with np.errstate(divide='ignore', invalid='ignore'):
        zscore = np.where(stds > 1e-12, (curr - means) / stds, 0.0)
        zscore[nan_mask] = np.nan
    return zscore


@ts_primitive
def ts_argmax(windows: np.ndarray) -> np.ndarray:
    """Relative 1-based index position of maximum value within rolling window d."""
    nan_mask = np.isnan(windows).any(axis=1)
    idx = np.argmax(windows, axis=1).astype(np.float64) + 1.0
    idx[nan_mask] = np.nan
    return idx


@ts_primitive
def ts_argmin(windows: np.ndarray) -> np.ndarray:
    """Relative 1-based index position of minimum value within rolling window d."""
    nan_mask = np.isnan(windows).any(axis=1)
    idx = np.argmin(windows, axis=1).astype(np.float64) + 1.0
    idx[nan_mask] = np.nan
    return idx
