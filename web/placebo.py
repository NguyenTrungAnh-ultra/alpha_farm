"""
Read-only view of the placebo walk-forward result folder (`<results>/WALKFORWARD_DIR`).

Nothing here writes: a missing or half-written summary.csv gives an empty view.
"""

import math
import os
from typing import Dict, List, Optional

import pandas as pd

from strategy_workflows.SearchConfigs import feedback_records, summarize_feedback
from strategy_workflows.WalkForward import RUN_KEY

WALKFORWARD_DIR = os.path.join('walkforward', 'llm_mcts')
SUMMARY_FILE = 'summary.csv'
PLACEBO_MODE = 'placebo'
REAL_MODE = 'real'
RUNS_FILE = 'runs.csv'


def walkforward_dir(root: str) -> str:
    return os.path.join(root, WALKFORWARD_DIR)


def read_summary(folder: str) -> pd.DataFrame:
    """summary.csv with sharpe numeric; rows without a mode or a finite Sharpe dropped; empty frame when unreadable."""
    path = os.path.join(folder, SUMMARY_FILE)
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame()
    if not {'mode', 'sharpe'} <= set(frame.columns):
        return pd.DataFrame()
    frame['sharpe'] = pd.to_numeric(frame['sharpe'], errors='coerce')
    return frame.dropna(subset=['mode', 'sharpe']).reset_index(drop=True)


def read_feedback(folder: str) -> Optional[Dict]:
    """
    Feedback-round statistics of the placebo runs in runs.csv (`SearchConfigs.summarize_feedback`, the numbers
    `walkforward summary` prints); None when runs.csv or its `feedback` column is missing.
    """
    try:
        frame = pd.read_csv(os.path.join(folder, RUNS_FILE))
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return None
    if not {'feedback', *RUN_KEY} <= set(frame.columns):
        return None
    return summarize_feedback(feedback_records(frame[frame['mode'] == PLACEBO_MODE], RUN_KEY))


def placebo_view(summary: pd.DataFrame) -> Optional[Dict]:
    """
    Placebo Sharpe distribution and the p-value. p is computed from the sets and the real Sharpe, not read
    from the file, as (1 + #sets with Sharpe >= real) / (K + 1); None while there is no real run.
    `min_p` is the smallest p reachable with K sets, and `needed` the real Sharpe that reaches it.
    """
    if summary.empty:
        return None
    placebo = summary[summary['mode'] == PLACEBO_MODE].sort_values('placebo_set' if 'placebo_set' in summary.columns
                                                                    else 'sharpe')
    if placebo.empty:
        return None
    sharpes = placebo['sharpe'].astype(float)
    k = len(sharpes)
    real = summary[summary['mode'] == REAL_MODE]
    real_sharpe = float(real['sharpe'].iloc[0]) if not real.empty else None
    p = None if real_sharpe is None else (1 + int((sharpes >= real_sharpe).sum())) / (k + 1)
    sets: List[Dict] = []
    for _, row in placebo.iterrows():
        sets.append({'set': int(row['placebo_set']) if 'placebo_set' in placebo.columns and pd.notna(row['placebo_set'])
                     else len(sets) + 1,
                     'n_days': _int(row.get('n_days')), 'n_windows': _int(row.get('n_windows')),
                     'sharpe': float(row['sharpe'])})
    return {'sets': sets, 'k': k, 'mean': float(sharpes.mean()), 'sd': float(sharpes.std()) if k > 1 else float('nan'),
            'min': float(sharpes.min()), 'max': float(sharpes.max()), 'real': real_sharpe, 'p': p,
            'min_p': 1 / (k + 1)}


def _int(value) -> Optional[int]:
    return None if value is None or (isinstance(value, float) and not math.isfinite(value)) else int(value)


def chart_points(view: Dict) -> Dict:
    """Chart data: one [set, Sharpe] pair per placebo set, the largest placebo Sharpe and the real Sharpe (or None)."""
    return {'points': [[s['set'], s['sharpe']] for s in view['sets']], 'max': view['max'], 'real': view['real']}
