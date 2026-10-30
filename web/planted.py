"""
Read-only view of the thesis planted-signal result folder (`<results>/THESIS_PLANTED_DIR`).

Nothing here writes: files are opened for reading only, and missing or half-written files give empty
results. Only the one folder named by THESIS_PLANTED_DIR is ever read.
"""

import json
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from strategy_workflows.PlantedSignal import NEAR_CORRELATION, Segments
from strategy_workflows.RunPlantedSignal import RUN_KEY, summarize_runs

THESIS_PLANTED_DIR = 'planted_window1'
FORMULA_FILE = 'planted_formula.json'
POSITIONS_FILE = 'positions_vs_a.json'
BOOL_COLUMNS = ('exact', 'near')
NUMERIC_COLUMNS = ('strength', 'seed', 'ic_search', 'ic_eval', 'closest_corr', 'closest_val_rank', 'best_corr',
                   'oos_sharpe', 'elapsed_s')
SEED_TABLE_COLUMNS = ('strength', 'seed', 'best_corr', 'exact', 'near', 'oos_sharpe', 'closest_expr', 'closest_corr',
                      'closest_val_rank')
# Position-comparison records keep these keys only.
POSITION_KEYS = ('strength', 'seed', 'best_pos_corr', 'best_agree_active', 'closest_corr', 'a_flat_share')


def thesis_dir(root: str) -> str:
    return os.path.join(root, THESIS_PLANTED_DIR)


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval of a binomial proportion (95% by default); (nan, nan) when n == 0."""
    if n <= 0:
        return float('nan'), float('nan')
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def read_segments(folder: str) -> Segments:
    """Segments of the folder; a missing or unreadable segments.json means the default split."""
    try:
        with open(os.path.join(folder, 'segments.json'), 'r', encoding='utf-8') as f:
            return Segments.from_dict(json.load(f))
    except (OSError, ValueError, KeyError, TypeError):
        return Segments()


def read_json(path: str):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_formula_expr(folder: str) -> Optional[str]:
    """Expression text of the planted formula; None when the file is missing or unreadable."""
    data = read_json(os.path.join(folder, FORMULA_FILE))
    return str(data['expression']) if isinstance(data, dict) and 'expression' in data else None


def read_runs(folder: str) -> pd.DataFrame:
    """
    runs.csv cleaned for aggregation: numeric columns coerced, exact/near as bool, rows without a
    key or without the last column (a half-written row) dropped, RUN_KEY columns filled when absent.
    """
    path = os.path.join(folder, 'runs.csv')
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        runs = pd.read_csv(path, on_bad_lines='skip')
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame()
    if runs.empty or not {'strength', 'seed'} <= set(runs.columns):
        return pd.DataFrame()
    if 'reward_mode' not in runs.columns:
        runs['reward_mode'] = '?'
    if 'iterations' not in runs.columns:
        runs['iterations'] = np.nan
    for column in NUMERIC_COLUMNS:
        if column in runs.columns:
            runs[column] = pd.to_numeric(runs[column], errors='coerce')
    for column in BOOL_COLUMNS:
        if column in runs.columns:
            runs[column] = runs[column].map(lambda v: str(v).strip().lower() == 'true')
    runs = runs.dropna(subset=['strength', 'seed', 'reward_mode'])
    if 'elapsed_s' in runs.columns:
        runs = runs.dropna(subset=['elapsed_s'])
    return runs.reset_index(drop=True)


def strength_table(runs: pd.DataFrame) -> List[Dict]:
    """One dict per target IC from `summarize_runs`, plus the 95% Wilson interval of the near-recovery rate."""
    if runs.empty:
        return []
    rows = []
    for row in summarize_runs(runs).sort_values('strength').to_dict('records'):
        n, near = int(row['n_runs']), int(row['near_count'])
        row['n_runs'], row['near_count'], row['exact_count'] = n, near, int(row['exact_count'])
        row['near_low'], row['near_high'] = wilson_interval(near, n)
        rows.append(row)
    return rows


def seed_table(runs: pd.DataFrame) -> List[Dict]:
    """One dict per run (the last of each key), ordered by target IC then seed."""
    if runs.empty:
        return []
    runs = runs.drop_duplicates(subset=RUN_KEY, keep='last').sort_values(['strength', 'seed'])
    rows = []
    for _, row in runs.iterrows():
        item = {c: row[c] for c in SEED_TABLE_COLUMNS if c in runs.columns}
        item['seed'] = int(item['seed'])
        rows.append(item)
    return rows


def read_positions(folder: str) -> List[Dict]:
    """Records of the position comparison with A; empty when the file is missing or malformed."""
    data = read_json(os.path.join(folder, POSITIONS_FILE))
    if not isinstance(data, list):
        return []
    return [{k: record.get(k) for k in POSITION_KEYS} for record in data
            if isinstance(record, dict) and {'strength', 'best_pos_corr'} <= set(record)]


def position_table(records: List[Dict]) -> List[Dict]:
    """Per target IC: number of seeds and mean / min / max of the best top-5 position correlation with A."""
    if not records:
        return []
    frame = pd.DataFrame(records)
    frame['best_pos_corr'] = pd.to_numeric(frame['best_pos_corr'], errors='coerce')
    rows = []
    for strength, sub in frame.groupby('strength'):
        values = sub['best_pos_corr'].dropna()
        rows.append({'strength': float(strength), 'n': int(len(values)),
                     'mean': float(values.mean()) if len(values) else float('nan'),
                     'min': float(values.min()) if len(values) else float('nan'),
                     'max': float(values.max()) if len(values) else float('nan')})
    return sorted(rows, key=lambda r: r['strength'])


def present_values(runs: pd.DataFrame, column: str) -> List[float]:
    """Sorted distinct values of `column` in runs.csv."""
    if runs.empty or column not in runs.columns:
        return []
    return sorted(float(v) for v in pd.to_numeric(runs[column], errors='coerce').dropna().unique())


def closest_points(seed_rows: List[Dict]) -> List[Dict]:
    """[{x: target IC, y: closest_corr, top5}] per seed; top5 = the closest candidate's validation rank is <= 5."""
    points = []
    for r in seed_rows:
        if 'closest_corr' not in r:
            continue
        rank = r.get('closest_val_rank')
        points.append({'x': float(r['strength']), 'y': None if pd.isna(r['closest_corr']) else float(r['closest_corr']),
                       'top5': bool(rank is not None and not pd.isna(rank) and rank <= 5)})
    return points


def near_chart_points(rows: List[Dict]) -> List[List[Optional[float]]]:
    """[target IC, rate, low, high] per row; non-finite values become None."""
    def clean(v):
        return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else float(v)
    return [[clean(r['strength']), clean(r['near_rate']), clean(r['near_low']), clean(r['near_high'])] for r in rows]


def near_threshold() -> float:
    return NEAR_CORRELATION
