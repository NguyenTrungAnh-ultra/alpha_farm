"""
Statistics
==========
Small statistical tools of the RQ1 comparison and of the thesis web.

    wilson_interval              Wilson score interval of a binomial proportion
    fisher_p_greater             one-sided Fisher exact p of a near-recovery count against a base count
    detection_threshold          lowest target IC > 0 whose one-sided Fisher p against IC 0 is below FISHER_ALPHA
    holm_adjust                  Holm step-down adjustment of a family of p-values
    stationary_bootstrap_indices Politis-Romano (1994) stationary bootstrap resample indices
    paired_sharpe_bootstrap      confidence interval of the difference of two annualised Sharpe ratios on the same days
"""

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import fisher_exact

TRADING_DAYS_PER_YEAR = 252
BOOTSTRAP_MEAN_BLOCK = 10
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261031
_CHUNK = 500
FISHER_ALPHA = 0.05


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval of a binomial proportion (95% by default); (nan, nan) when n == 0."""
    if n <= 0:
        return float('nan'), float('nan')
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def fisher_p_greater(near: int, n: int, base_near: int, base_n: int) -> float:
    """One-sided Fisher exact p: chance of at least `near` of `n` near recoveries if the level's rate equalled the base rate."""
    if n <= 0 or base_n <= 0:
        return float('nan')
    return float(fisher_exact([[near, n - near], [base_near, base_n - base_near]], alternative='greater')[1])


def detection_threshold(rows: List[Dict]) -> Optional[Dict]:
    """
    Row of the lowest target IC > 0 whose one-sided Fisher p against IC 0 is below FISHER_ALPHA; None if none.
    Rows are dicts with `strength` (target IC, ascending) and `p_fisher` (None for IC 0).
    """
    return next((r for r in rows if r['strength'] > 0 and r.get('p_fisher') is not None
                 and math.isfinite(r['p_fisher']) and r['p_fisher'] < FISHER_ALPHA), None)


def holm_adjust(p_values: Sequence[float]) -> List[float]:
    """Holm-adjusted p-values in the input order: sorted ascending, p_(i) * (m - i + 1), made monotone, capped at 1."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted


def stationary_bootstrap_indices(n: int, size: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """
    `size` resamples of the indices 0..n-1, each of length n, as blocks of geometric length with mean `mean_block`:
    every step starts a new block at a uniform index with probability 1 / mean_block, otherwise continues the
    current block at the next index (wrapping around the end).
    """
    if n < 1 or mean_block < 1:
        raise ValueError(f"need n >= 1 and mean block >= 1, got {n}, {mean_block}")
    starts = rng.integers(0, n, size=(size, n))
    restart = rng.random((size, n)) < 1.0 / mean_block
    restart[:, 0] = True
    t = np.arange(n)
    last_restart = np.maximum.accumulate(np.where(restart, t, 0), axis=1)
    base = np.take_along_axis(starts, last_restart, axis=1)
    return (base + t - last_restart) % n


def sharpe_rows(values: np.ndarray) -> np.ndarray:
    """Annualised Sharpe (mean / std with ddof 0 * sqrt(252)) of every row; NaN where the row is constant."""
    std = values.std(axis=1)
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(std > 0, values.mean(axis=1) / std * np.sqrt(TRADING_DAYS_PER_YEAR), np.nan)


def paired_sharpe_bootstrap(
    first: np.ndarray, second: np.ndarray, mean_block: float = BOOTSTRAP_MEAN_BLOCK,
    n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED, level: float = 0.95,
) -> Dict[str, float]:
    """
    Sharpe(first) - Sharpe(second) on the same days with a percentile interval from a paired stationary block
    bootstrap: both series are resampled with the same indices, so their dependence is kept. Also the Pearson
    correlation of the two daily series. Resamples whose Sharpe is undefined are left out of the interval.
    """
    first, second = np.asarray(first, dtype=np.float64), np.asarray(second, dtype=np.float64)
    if first.shape != second.shape or first.ndim != 1 or len(first) < 2:
        raise ValueError("need two 1-D series of equal length >= 2")
    n = len(first)
    rng = np.random.default_rng(seed)
    differences = []
    for done in range(0, n_resamples, _CHUNK):
        idx = stationary_bootstrap_indices(n, min(_CHUNK, n_resamples - done), mean_block, rng)
        differences.append(sharpe_rows(first[idx]) - sharpe_rows(second[idx]))
    differences = np.concatenate(differences)
    differences = differences[~np.isnan(differences)]
    tail = 100.0 * (1.0 - level) / 2.0
    point = sharpe_rows(first[None, :])[0] - sharpe_rows(second[None, :])[0]
    constant = first.std() == 0 or second.std() == 0
    return {
        'n_days': n, 'difference': float(point),
        'ci_low': float(np.percentile(differences, tail)) if len(differences) else float('nan'),
        'ci_high': float(np.percentile(differences, 100.0 - tail)) if len(differences) else float('nan'),
        'rho': float('nan') if constant else float(np.corrcoef(first, second)[0, 1]),
    }
