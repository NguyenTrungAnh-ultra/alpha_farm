"""
Chart data for the browser (Chart.js renders it). Everything returned is plain JSON-safe Python:
NaN / inf become None, series are thinned to at most MAX_POINTS.
"""

import math
from typing import Dict, Sequence

import pandas as pd

MAX_POINTS = 1500


def clean(value):
    """Floats that JSON cannot carry (NaN, inf) become None; numpy scalars become Python numbers."""
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


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
