"""
tests/test_alpha_primitives.py

Pytest suite for core_engine.AlphaPrimitives.
Verifies all 9 primitives for Series/ndarray inputs, index preservation,
NaN padding, edge cases, error handling, and mathematical accuracy vs Pandas.
"""

import pytest
import numpy as np
import pandas as pd

from core_engine.AlphaPrimitives import (
    ts_mean, ts_sum, ts_max, ts_min,
    ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
)


@pytest.fixture
def sample_series():
    dates = pd.date_range("2024-01-01", periods=100, freq="1h")
    np.random.seed(42)
    vals = 100.0 + np.cumsum(np.random.randn(100))
    return pd.Series(vals, index=dates, name="close")


@pytest.fixture
def sample_pair_series():
    dates = pd.date_range("2024-01-01", periods=100, freq="1h")
    np.random.seed(42)
    vals_x = 100.0 + np.cumsum(np.random.randn(100))
    vals_y = 50.0 + np.cumsum(np.random.randn(100))
    return (
        pd.Series(vals_x, index=dates, name="x"),
        pd.Series(vals_y, index=dates, name="y")
    )


def test_series_preservation(sample_series):
    d = 10
    res = ts_mean(sample_series, d)
    assert isinstance(res, pd.Series)
    assert res.name == sample_series.name
    assert (res.index == sample_series.index).all()
    assert len(res) == len(sample_series)
    assert res.iloc[: d - 1].isna().all()
    assert not res.iloc[d - 1 :].isna().any()


def test_ndarray_input(sample_series):
    d = 10
    arr = sample_series.values
    res = ts_mean(arr, d)
    assert isinstance(res, np.ndarray)
    assert res.ndim == 1
    assert len(res) == len(arr)
    assert np.isnan(res[: d - 1]).all()
    assert not np.isnan(res[d - 1 :]).any()


def test_all_primitives_pandas_equivalence(sample_series, sample_pair_series):
    x = sample_series
    x_pair, y_pair = sample_pair_series
    d = 20

    # 1. ts_mean
    res_mean = ts_mean(x, d)
    expected_mean = x.rolling(d, min_periods=d).mean()
    np.testing.assert_allclose(res_mean, expected_mean, rtol=1e-5, atol=1e-5, equal_nan=True)

    # 2. ts_sum
    res_sum = ts_sum(x, d)
    expected_sum = x.rolling(d, min_periods=d).sum()
    np.testing.assert_allclose(res_sum, expected_sum, rtol=1e-5, atol=1e-5, equal_nan=True)

    # 3. ts_max
    res_max = ts_max(x, d)
    expected_max = x.rolling(d, min_periods=d).max()
    np.testing.assert_allclose(res_max, expected_max, rtol=1e-5, atol=1e-5, equal_nan=True)

    # 4. ts_min
    res_min = ts_min(x, d)
    expected_min = x.rolling(d, min_periods=d).min()
    np.testing.assert_allclose(res_min, expected_min, rtol=1e-5, atol=1e-5, equal_nan=True)

    # 5. ts_rank
    res_rank = ts_rank(x, d)
    expected_rank = x.rolling(d, min_periods=d).apply(lambda w: float(w.rank(pct=True).iloc[-1]), raw=False)
    np.testing.assert_allclose(res_rank, expected_rank, rtol=1e-5, atol=1e-5, equal_nan=True)

    # 6. ts_corr
    res_corr = ts_corr(x_pair, y_pair, d)
    expected_corr = x_pair.rolling(d, min_periods=d).corr(y_pair)
    np.testing.assert_allclose(res_corr, expected_corr, rtol=1e-5, atol=1e-5, equal_nan=True)

    # 7. ts_zscore
    res_zscore = ts_zscore(x, d)
    expected_zscore = (x - x.rolling(d, min_periods=d).mean()) / x.rolling(d, min_periods=d).std(ddof=1)
    expected_zscore = expected_zscore.replace([np.inf, -np.inf], np.nan)
    np.testing.assert_allclose(res_zscore, expected_zscore, rtol=1e-5, atol=1e-5, equal_nan=True)

    # 8. ts_argmax
    res_argmax = ts_argmax(x, d)
    expected_argmax = x.rolling(d, min_periods=d).apply(lambda w: float(np.argmax(w)) + 1.0, raw=True)
    np.testing.assert_allclose(res_argmax, expected_argmax, rtol=1e-5, atol=1e-5, equal_nan=True)

    # 9. ts_argmin
    res_argmin = ts_argmin(x, d)
    expected_argmin = x.rolling(d, min_periods=d).apply(lambda w: float(np.argmin(w)) + 1.0, raw=True)
    np.testing.assert_allclose(res_argmin, expected_argmin, rtol=1e-5, atol=1e-5, equal_nan=True)


def test_invalid_window_raises_error(sample_series):
    with pytest.raises(ValueError):
        ts_mean(sample_series, 0)
    with pytest.raises(ValueError):
        ts_mean(sample_series, -5)
    with pytest.raises(ValueError):
        ts_mean(sample_series, 5.5)  # non-int
    with pytest.raises(ValueError):
        ts_mean(sample_series, True)  # boolean


def test_window_larger_than_length(sample_series):
    N = len(sample_series)
    res = ts_mean(sample_series, N + 10)
    assert len(res) == N
    assert res.isna().all()


def test_empty_series():
    s = pd.Series([], dtype=float)
    res = ts_mean(s, 5)
    assert len(res) == 0
    assert isinstance(res, pd.Series)


def test_dimension_mismatch_raises_error():
    x = np.ones(10)
    y = np.ones(20)
    with pytest.raises(ValueError):
        ts_corr(x, y, 5)


def test_non_1d_input():
    x_2d = np.ones((10, 5))
    with pytest.raises(ValueError):
        ts_mean(x_2d, 3)


def test_zero_variance_handling():
    flat_series = pd.Series(np.full(50, 10.0))
    res_zscore = ts_zscore(flat_series, 10)
    # Window of constant values has std 0 -> zscore returns 0.0 for non-nan region
    assert np.isnan(res_zscore.iloc[:9]).all()
    assert (res_zscore.iloc[9:] == 0.0).all()

    flat_series_y = pd.Series(np.full(50, 5.0))
    res_corr = ts_corr(flat_series, flat_series_y, 10)
    # Constant series correlation yields NaN
    assert res_corr.iloc[9:].isna().all()
