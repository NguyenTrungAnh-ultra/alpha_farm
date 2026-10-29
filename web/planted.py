"""
Read-only view of the planted-signal result folders (`<results>/planted*/`).

Nothing here writes: files are opened for reading only, and missing or half-written files give empty
results. A folder name coming from a URL is only ever matched against the folders found on disk.
"""

import json
import os
import re
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from strategy_workflows.PlantedSignal import Segments
from strategy_workflows.RunPlantedSignal import RUN_KEY, summarize_runs

# A search whose log/runs.csv has not been touched for this long is shown as stopped, not running.
RUNNING_FRESH_S = 6 * 3600
RUN_COUNT_PATTERN = re.compile(r'\[planted\] (\d+) runs')
BOOL_COLUMNS = ('exact', 'near')
NUMERIC_COLUMNS = ('strength', 'seed', 'ic_search', 'ic_eval', 'closest_corr', 'closest_train_rank',
                   'closest_val_rank', 'oos_sharpe', 'elapsed_s')
SEED_TABLE_COLUMNS = ('reward_mode', 'strength', 'seed', 'closest_expr', 'closest_corr', 'closest_train_rank',
                      'closest_val_rank', 'exact', 'near', 'oos_sharpe')


def list_dirs(root: str) -> List[str]:
    """Names of the `planted*` folders directly under `root`, sorted."""
    if not os.path.isdir(root):
        return []
    return sorted(n for n in os.listdir(root) if n.startswith('planted') and os.path.isdir(os.path.join(root, n)))


def resolve_dir(root: str, name: str) -> Optional[str]:
    """Absolute folder path when `name` is exactly one of the listed folders, else None."""
    return os.path.join(root, name) if name in list_dirs(root) else None


def read_segments(folder: str) -> Segments:
    """Segments of the folder; a missing or unreadable segments.json means the default split."""
    try:
        with open(os.path.join(folder, 'segments.json'), 'r', encoding='utf-8') as f:
            return Segments.from_dict(json.load(f))
    except (OSError, ValueError, KeyError, TypeError):
        return Segments()


def _read_csv(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path, on_bad_lines='skip')
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def read_runs(folder: str) -> pd.DataFrame:
    """
    runs.csv cleaned for aggregation: numeric columns coerced, exact/near as bool, rows without a
    key or without the last column (a half-written row) dropped, RUN_KEY columns filled when absent.
    """
    runs = _read_csv(os.path.join(folder, 'runs.csv'))
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


def read_oracle(folder: str) -> pd.DataFrame:
    return _read_csv(os.path.join(folder, 'oracle.csv'))


def expected_runs(folder: str) -> Optional[int]:
    """Total runs announced by the search ("[planted] N runs" line of search.log); None when absent."""
    path = os.path.join(folder, 'search.log')
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'rb') as f:
            text = f.read().decode('utf-8', errors='replace')
    except OSError:
        return None
    found = RUN_COUNT_PATTERN.findall(text)
    return int(found[-1]) if found else None


def _mtime(path: str) -> Optional[float]:
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def folder_info(folder: str, now: Optional[float] = None) -> Dict:
    """Overview of one folder: segments, reward modes, runs done / expected, running flag."""
    now = time.time() if now is None else now
    runs = read_runs(folder)
    done = len(runs.drop_duplicates(subset=RUN_KEY, keep='last')) if not runs.empty else 0
    modes = sorted(runs['reward_mode'].unique()) if not runs.empty else []
    expected = expected_runs(folder)
    expected_is_estimate = False
    oracle = read_oracle(folder)
    has_log = os.path.exists(os.path.join(folder, 'search.log'))
    # Without the announcing log line, one oracle row per (strength, seed) is the best guess of the run count.
    if expected is None and has_log and len(modes) <= 1 and not oracle.empty:
        expected, expected_is_estimate = len(oracle), True
    log_time = _mtime(os.path.join(folder, 'search.log'))
    runs_time = _mtime(os.path.join(folder, 'runs.csv'))
    summary_time = _mtime(os.path.join(folder, 'summary.csv'))
    if expected is not None:
        complete = done >= expected
    else:
        complete = summary_time is not None and runs_time is not None and summary_time >= runs_time
    last_touch = max([t for t in (log_time, runs_time) if t is not None], default=None)
    running = (log_time is not None and not complete and last_touch is not None
               and now - last_touch < RUNNING_FRESH_S)
    return {
        'name': os.path.basename(folder), 'segments': read_segments(folder).to_dict(), 'modes': modes,
        'done': done, 'expected': expected, 'expected_is_estimate': expected_is_estimate,
        'running': running, 'has_runs': not runs.empty, 'has_oracle': not oracle.empty,
    }


def strength_table(runs: pd.DataFrame) -> pd.DataFrame:
    """Per (reward_mode, strength) table from the same aggregation `main.py planted summary` uses."""
    return summarize_runs(runs) if not runs.empty else pd.DataFrame()


def seed_table(runs: pd.DataFrame) -> List[Dict]:
    """One dict per run (the last of each key), with the top expressions parsed from their JSON list."""
    if runs.empty:
        return []
    runs = runs.drop_duplicates(subset=RUN_KEY, keep='last').sort_values(['reward_mode', 'strength', 'seed'])
    rows = []
    for _, row in runs.iterrows():
        item = {c: row[c] for c in SEED_TABLE_COLUMNS if c in runs.columns}
        item['top_exprs'] = _json_list(row.get('top_exprs'))
        rows.append(item)
    return rows


def _json_list(value) -> List[str]:
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(v) for v in parsed] if isinstance(parsed, list) else []


def present_values(runs: pd.DataFrame, oracle: pd.DataFrame, column: str) -> List[float]:
    """Sorted distinct values of `column` found in runs.csv and oracle.csv."""
    values = set()
    for frame in (runs, oracle):
        if not frame.empty and column in frame.columns:
            values.update(float(v) for v in pd.to_numeric(frame[column], errors='coerce').dropna())
    return sorted(values)


def run_mode(runs: pd.DataFrame, strength: float, seed: int) -> str:
    """Reward mode of the run at (strength, seed); 'soft' when that run is not in runs.csv."""
    if runs.empty:
        return 'soft'
    match = runs[np.isclose(runs['strength'], strength) & (runs['seed'] == seed)]
    return str(match['reward_mode'].iloc[-1]) if not match.empty else 'soft'
