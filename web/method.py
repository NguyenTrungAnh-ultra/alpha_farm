"""
Read-only facts for the method and data pages: walk-forward windows, bar counts per segment taken
from the data file, and the summary of the frozen blueprint set.
"""

import json
import os
from collections import Counter
from functools import lru_cache
from typing import Dict, List, Optional

import pandas as pd

from core_engine.BacktestEngine import load_data
from strategy_workflows.WalkForward import WINDOWS

TIMEFRAME = '60m'
BLUEPRINT_SET = os.path.join('blueprint_sets', '20261029_212813', 'blueprints.json')


@lru_cache(maxsize=1)
def _bar_index() -> Optional[pd.DatetimeIndex]:
    """Timestamps of every bar in the 60m file; None when the file cannot be read."""
    try:
        return load_data(TIMEFRAME, start='1900-01-01', end='2100-12-31').index
    except (OSError, ValueError, KeyError):
        return None


def _count(index: pd.DatetimeIndex, start: str, end: str) -> int:
    """Bars with start <= date <= end (whole days)."""
    return int(((index >= pd.Timestamp(start)) & (index < pd.Timestamp(end) + pd.Timedelta(days=1))).sum())


def data_range() -> Optional[Dict]:
    index = _bar_index()
    if index is None or len(index) == 0:
        return None
    return {'first': index.min().strftime('%Y-%m-%d'), 'last': index.max().strftime('%Y-%m-%d'), 'bars': len(index)}


def window_rows(with_bars: bool = False) -> List[Dict]:
    """One dict per walk-forward window; bar counts only when `with_bars` and the data file is readable."""
    index = _bar_index() if with_bars else None
    rows = []
    for i, w in enumerate(WINDOWS, start=1):
        row = {'window': i, 'search_start': w.search_start, 'train_end': w.train_end,
               'validation_start': w.validation_start, 'search_end': w.search_end,
               'eval_start': w.eval_start, 'eval_end': w.eval_end, 'bars': None}
        if index is not None:
            row['bars'] = {'train': _count(index, w.search_start, w.train_end),
                           'validation': _count(index, w.validation_start, w.search_end),
                           'eval': _count(index, w.eval_start, w.eval_end)}
        rows.append(row)
    return rows


def blueprint_summary(results_root: str) -> Optional[Dict]:
    """Count and root operators of the frozen blueprint set; None when the file is missing or unreadable."""
    try:
        with open(os.path.join(results_root, BLUEPRINT_SET), 'r', encoding='utf-8') as f:
            blueprints = json.load(f)
        roots = Counter(str(b['macro_blueprint']).split('(')[0] for b in blueprints)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return {'count': len(blueprints), 'roots': sorted(roots.items(), key=lambda kv: (-kv[1], kv[0]))}


GANTT_WIDTH = 940
GANTT_LEFT = 60
GANTT_RIGHT = 20
GANTT_TOP = 44
GANTT_ROW = 30
GANTT_BAR = 18
GANTT_START = pd.Timestamp('2018-08-01')
GANTT_END = pd.Timestamp('2026-01-01')
SEGMENT_LABELS = {'train': 'học', 'validation': 'kiểm định', 'eval': 'đánh giá'}


def gantt_view() -> Dict:
    """
    Server-side geometry of the walk-forward timeline (SVG units): one row per window, three contiguous
    bars (train, validation, evaluation), year ticks and the out-of-sample band. Each bar carries a tooltip.
    """
    span = (GANTT_END - GANTT_START).days
    plot_width = GANTT_WIDTH - GANTT_LEFT - GANTT_RIGHT

    def x_of(day: pd.Timestamp) -> float:
        return GANTT_LEFT + plot_width * (day - GANTT_START).days / span

    rows = window_rows(with_bars=True)
    bars = []
    for i, w in enumerate(rows):
        y = GANTT_TOP + GANTT_ROW * i + (GANTT_ROW - GANTT_BAR) / 2
        spans = {'train': (w['search_start'], w['train_end']), 'validation': (w['validation_start'], w['search_end']),
                 'eval': (w['eval_start'], w['eval_end'])}
        for kind, (start, end) in spans.items():
            x1, x2 = x_of(pd.Timestamp(start)), x_of(pd.Timestamp(end) + pd.Timedelta(days=1))
            tip = f"Cửa sổ {w['window']}, {SEGMENT_LABELS[kind]}: {start} → {end}"
            if w['bars']:
                tip += f" ({w['bars'][kind]} nến)"
            bars.append({'kind': kind, 'x': round(x1, 1), 'y': y, 'w': round(x2 - x1, 1), 'h': GANTT_BAR, 'tip': tip})
    ticks = [{'x': round(x_of(pd.Timestamp(year=y, month=1, day=1)), 1), 'label': str(y)}
             for y in range(GANTT_START.year + 1, GANTT_END.year + 1)]
    first_eval, last_eval = pd.Timestamp(rows[0]['eval_start']), pd.Timestamp(rows[-1]['eval_end'])
    height = GANTT_TOP + GANTT_ROW * len(rows) + 30
    return {'width': GANTT_WIDTH, 'height': height, 'bars': bars, 'ticks': ticks, 'rows': [
                {'label': w['window'], 'y': GANTT_TOP + GANTT_ROW * i + GANTT_ROW / 2 + 4} for i, w in enumerate(rows)],
            'oos': {'x': round(x_of(first_eval), 1), 'w': round(x_of(last_eval + pd.Timedelta(days=1)) - x_of(first_eval), 1),
                    'label': f"ngoài mẫu {first_eval:%Y-%m} → {last_eval:%Y-%m}"},
            'plot_top': GANTT_TOP - 6, 'plot_bottom': GANTT_TOP + GANTT_ROW * len(rows),
            'legend': [{'kind': k, 'label': v} for k, v in SEGMENT_LABELS.items()]}
