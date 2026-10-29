"""
Chart data for the browser (Chart.js renders it). Everything returned is plain JSON-safe Python:
NaN / inf become None, series are thinned to at most MAX_POINTS.
"""

import math
from typing import Dict, List, Optional, Sequence

import pandas as pd

MAX_POINTS = 1500


def clean(value):
    """Floats that JSON cannot carry (NaN, inf) become None; numpy scalars become Python numbers."""
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _thin(series: pd.Series) -> pd.Series:
    return series.iloc[::max(1, len(series) // MAX_POINTS)]


def comparison_data(entries: List[Dict]) -> Dict:
    """
    Data for the cross-folder charts. Each entry: {'name', 'strengths': summarize_runs table (may be empty),
    'oracle': oracle.csv frame (may be empty)}.
    'near' / 'oos': one series per (folder, reward mode) with points [ic, near_rate] / [ic, mean, std];
    'oracle': per folder, one line per reward column (mean over seeds per strength) as [ic, reward].
    """
    near, oos = [], []
    for entry in entries:
        table = entry['strengths']
        if table is None or table.empty:
            continue
        for mode, sub in table.groupby('reward_mode'):
            sub = sub.sort_values('ic_search')
            label = entry['name'] if table['reward_mode'].nunique() == 1 else f"{entry['name']} · {mode}"
            near.append({'label': label, 'points': [[clean(r.ic_search), clean(r.near_rate)] for r in sub.itertuples()]})
            oos.append({'label': label, 'points': [[clean(r.ic_search), clean(r.oos_sharpe_mean), clean(r.oos_sharpe_std)]
                                                  for r in sub.itertuples()]})
    return {'near': near, 'oos': oos, 'oracle': _oracle_data(entries)}


def _oracle_data(entries: List[Dict]) -> List[Dict]:
    panels = []
    for entry in entries:
        oracle = entry['oracle']
        if oracle is None or oracle.empty or 'strength' not in oracle.columns:
            continue
        columns = [c for c in oracle.columns if c.startswith('reward_') and not c.endswith('_val')]
        if not columns:
            continue
        ic_col = 'ic_search' if 'ic_search' in oracle.columns else 'strength'
        grouped = oracle.groupby('strength')[[ic_col] + columns].mean().sort_values(ic_col)
        lines = [{'label': c, 'points': [[clean(x), clean(y)] for x, y in zip(grouped[ic_col], grouped[c])]}
                 for c in columns]
        panels.append({'name': entry['name'], 'lines': lines})
    return panels


def time_series(series: Dict[str, pd.Series], markers: Sequence[tuple] = ()) -> Dict:
    """
    Series sharing one DatetimeIndex axis. Output: {'labels': [...], 'series': [{'label', 'values'}],
    'markers': [{'index', 'label'}]}; each marker (timestamp, label) points at the first label at or after it.
    """
    first = next(iter(series.values()))
    step = max(1, len(first) // MAX_POINTS)
    index = first.index[::step]
    out = {'labels': [t.strftime('%Y-%m-%d %H:%M') for t in index], 'series': [], 'markers': []}
    for label, values in series.items():
        out['series'].append({'label': label, 'values': [clean(v) for v in values.reindex(first.index).iloc[::step]]})
    for when, label in markers:
        position = int(index.searchsorted(pd.Timestamp(when)))
        out['markers'].append({'index': min(position, len(index) - 1), 'label': label})
    return out
