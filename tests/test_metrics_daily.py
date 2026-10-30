import numpy as np
import pandas as pd

from core_engine.BacktestEngine import BacktestResult
from core_engine.CalculateMetrics import compute_metrics

INITIAL = 1e9


def _result():
    # Day 1 (3 bars), a gap day with no bars, day 3 (2 bars), day 4 (3 bars, the last).
    idx = pd.DatetimeIndex([
        '2024-01-01 09:00', '2024-01-01 10:00', '2024-01-01 14:00',
        '2024-01-03 09:00', '2024-01-03 14:00',
        '2024-01-04 09:00', '2024-01-04 10:00', '2024-01-04 14:00',
    ])
    eq = pd.Series(INITIAL + np.array([1e6, 5e6, 2e6, -3e6, 4e6, 9e6, -8e6, 6e6]), index=idx)
    return BacktestResult(eq, eq, [], INITIAL, float(eq.iloc[-1]), 0.0, 0, 0.0), eq


def test_daily_selection_matches_resample():
    result, eq = _result()
    daily = eq.resample('D').last().dropna()
    assert len(daily) == 3
    rets = daily.diff().fillna(0.0) / INITIAL
    dd = (daily - daily.cummax()) / daily.cummax()

    m = compute_metrics(result)
    assert m['sharpe_ratio'] == rets.mean() / rets.std(ddof=0) * np.sqrt(252)
    assert m['volatility'] == rets.std(ddof=1) * np.sqrt(252)
    assert m['max_drawdown_pct'] == dd.min() * 100
    assert m['ulcer_index'] == np.sqrt((dd ** 2).mean())
    assert m['cumulative_return_pct'] == (daily.iloc[-1] / INITIAL - 1) * 100
    # Last day's last bar (6e6) must be the final daily value, not an intraday one.
    assert daily.iloc[-1] == INITIAL + 6e6
