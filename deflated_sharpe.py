"""
Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) over the real-data out-of-sample daily returns
of the frozen walk-forward run. Trials = one daily series per (system, seed), mode == 'real'.

All Sharpe ratios inside the formulas are per-period (daily, not annualised). The daily Sharpe uses
ddof 0 like `WalkForward.annualised_sharpe`, so daily * sqrt(252) equals the annual column; the
variance across trials uses ddof 1. Kurtosis is raw (normal = 3).
"""
from pathlib import Path
from typing import List, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from strategy_workflows.WalkForward import TRADING_DAYS_PER_YEAR, annualised_sharpe

ROOT = Path(__file__).resolve().parent / 'results' / 'walkforward'
SYSTEMS = ('llm_mcts', 'mcts_only', 'random', 'llm_only', 'buy_hold', 'tsmom')
EULER_GAMMA = 0.5772156649015329


def daily_sharpe(returns: Sequence[float]) -> float:
    """mean / std (ddof 0) of daily returns, not annualised; NaN when flat or shorter than 2."""
    values = np.asarray(returns, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < 2 or values.std(ddof=0) == 0:
        return float('nan')
    return float(values.mean() / values.std(ddof=0))


def probabilistic_sharpe(returns: Sequence[float], benchmark: float = 0.0) -> float:
    """PSR: probability that the true daily Sharpe exceeds `benchmark` (daily units)."""
    values = np.asarray(returns, dtype=float)
    values = values[~np.isnan(values)]
    sharpe = daily_sharpe(values)
    if np.isnan(sharpe):
        return float('nan')
    skew = float(stats.skew(values))
    kurt = float(stats.kurtosis(values, fisher=False))
    denominator = 1.0 - skew * sharpe + (kurt - 1.0) / 4.0 * sharpe ** 2
    if denominator <= 0:
        return float('nan')
    return float(stats.norm.cdf((sharpe - benchmark) * np.sqrt(len(values) - 1) / np.sqrt(denominator)))


def expected_max_sharpe(sharpes: Sequence[float]) -> float:
    """SR0: expected maximum daily Sharpe among N null trials with the observed cross-trial variance."""
    values = np.asarray(sharpes, dtype=float)
    values = values[~np.isnan(values)]
    n = len(values)
    if n < 2:
        return 0.0
    scale = np.sqrt(values.var(ddof=1))
    return float(scale * ((1 - EULER_GAMMA) * stats.norm.ppf(1 - 1 / n)
                          + EULER_GAMMA * stats.norm.ppf(1 - 1 / (n * np.e))))


def deflated_sharpe(returns: Sequence[float], sharpes: Sequence[float]) -> float:
    """DSR: PSR of `returns` against the expected maximum Sharpe of the trials `sharpes`."""
    return probabilistic_sharpe(returns, expected_max_sharpe(sharpes))


def load_trials(root: Path = ROOT, systems: Sequence[str] = SYSTEMS) -> List[dict]:
    """One daily series per (system, seed) of mode 'real', averaged over duplicate dates as `summarize` does."""
    trials = []
    for system in systems:
        frame = pd.read_csv(root / system / 'returns.csv')
        frame = frame.drop_duplicates(subset=['date', 'window', 'seed', 'mode', 'placebo_set'], keep='last')
        real = frame[frame['mode'] == 'real']
        for seed, part in real.groupby('seed'):
            trials.append({'system': system, 'seed': int(seed),
                           'returns': part.groupby('date')['return'].mean().sort_index()})
    return trials


def build_table(trials: List[dict]) -> pd.DataFrame:
    sharpes = [daily_sharpe(t['returns']) for t in trials]
    sr0 = expected_max_sharpe(sharpes)
    rows = []
    for trial, sharpe in zip(trials, sharpes):
        values = trial['returns'].dropna().to_numpy()
        rows.append({'system': trial['system'], 'seed': trial['seed'], 'n_days': len(values),
                     'sharpe_annual': annualised_sharpe(trial['returns']), 'sharpe_daily': sharpe,
                     'skew': float(stats.skew(values)), 'kurtosis': float(stats.kurtosis(values, fisher=False)),
                     'psr_zero': probabilistic_sharpe(values, 0.0),
                     'dsr': probabilistic_sharpe(values, sr0)})
    return pd.DataFrame(rows)


def main() -> None:
    trials = load_trials()
    table = build_table(trials)
    sharpes = table['sharpe_daily'].to_numpy()
    sr0 = expected_max_sharpe(sharpes)
    annual_check = float(np.nanmax(np.abs(table['sharpe_daily'] * np.sqrt(TRADING_DAYS_PER_YEAR)
                                          - table['sharpe_annual'])))
    out = ROOT / 'dsr.csv'
    table.to_csv(out, index=False)
    with pd.option_context('display.width', 200, 'display.float_format', '{:.4f}'.format):
        print(table.to_string(index=False))
    print(f"N = {len(sharpes)}, V = {np.var(sharpes, ddof=1):.6g}, "
          f"SR0 daily = {sr0:.6f}, SR0 x sqrt(252) = {sr0 * np.sqrt(TRADING_DAYS_PER_YEAR):.4f}")
    print(f"max |daily*sqrt(252) - sharpe_annual| = {annual_check:.2e}")
    print(f"written {out}")


if __name__ == '__main__':
    main()
