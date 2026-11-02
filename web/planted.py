"""
Read-only view of the planted-signal result folder of the RQ1 system (`<results>/THESIS_PLANTED_DIR`).

Nothing here writes: files are opened for reading only, and missing or half-written files give empty
results. Only the one folder named by THESIS_PLANTED_DIR is ever read.
"""

import json
import math
import os
from typing import Dict, List, Optional

import pandas as pd

from strategy_workflows.PlantedSignal import Segments
from strategy_workflows.RunRQ1 import DETECTION_BUDGET, DETECTION_CONFIG
from strategy_workflows.Statistics import fisher_p_greater, wilson_interval

THESIS_PLANTED_DIR = 'planted_rq1'
FORMULAS_FILE = 'planted_formulas.json'
DETECTION_FILE = 'detection_thresholds.csv'
SUMMARY_FILE = 'summary.csv'
RUNS_FILE = 'runs.csv'
A_NAMES = ('A1', 'A2', 'A3', 'A4')
A_KINDS = {'classical': 'kinh điển', 'random': 'lạ (sinh ngẫu nhiên)'}


def thesis_dir(root: str) -> str:
    return os.path.join(root, THESIS_PLANTED_DIR)


def read_json(path: str):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read_table(path: str, required: tuple = ()) -> pd.DataFrame:
    """A CSV as written by the RQ1 steps; an empty frame when it is missing, unreadable, empty or lacks `required`."""
    try:
        frame = pd.read_csv(path, on_bad_lines='skip')
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError):
        return pd.DataFrame()
    return frame if not frame.empty and set(required) <= set(frame.columns) else pd.DataFrame()


def read_segments(folder: str) -> Segments:
    """Segments of the folder; a missing or unreadable segments.json means the default split."""
    try:
        with open(os.path.join(folder, 'segments.json'), 'r', encoding='utf-8') as f:
            return Segments.from_dict(json.load(f))
    except (OSError, ValueError, KeyError, TypeError):
        return Segments()


def _count_operators(node) -> int:
    """Operators in a stored formula tree: nodes with children."""
    if not isinstance(node, dict):
        return 0
    children = node.get('children') or []
    return (1 if children else 0) + sum(_count_operators(c) for c in children)


def _number(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_formulas(folder: str) -> List[Dict]:
    """The planted signals A: name, expression, type, operator count, ADF p and crowding share; empty when missing."""
    data = read_json(os.path.join(folder, FORMULAS_FILE))
    if not isinstance(data, dict):
        return []
    rows = []
    for name in sorted(data):
        item = data[name]
        if not isinstance(item, dict) or 'expression' not in item:
            continue
        selection = item.get('selection') if isinstance(item.get('selection'), dict) else {}
        rows.append({'name': name, 'expression': str(item['expression']), 'kind': selection.get('kind'),
                     'n_operators': _count_operators(item.get('tree')), 'z_window': item.get('z_window'),
                     'adf_p': _number(selection.get('adf_p')), 'crowding_share': _number(selection.get('crowding_share'))})
    return rows


def read_detection(folder: str) -> List[Dict]:
    """
    Detection thresholds of the primary configuration per A (detection_thresholds.csv): `threshold_ic` and
    `p_fisher` are None when no level passed, `rates` is the text of near counts per IC.
    """
    frame = read_table(os.path.join(folder, DETECTION_FILE), ('a', 'config', 'budget', 'threshold_ic', 'p_fisher'))
    rows = []
    for record in frame.to_dict('records'):
        rows.append({'a': str(record['a']), 'config': record['config'], 'budget': int(record['budget']),
                     'threshold_ic': _number(record['threshold_ic']), 'p_fisher': _number(record['p_fisher']),
                     'rates': str(record.get('rates', '')) if pd.notna(record.get('rates')) else ''})
    return sorted(rows, key=lambda r: r['a'])


SUMMARY_COLUMNS = ('config', 'ic', 'a', 'budget', 'n_runs', 'near_count')


def read_summary(folder: str) -> pd.DataFrame:
    """summary.csv with numeric counts; rows without a count dropped; empty frame when unreadable."""
    frame = read_table(os.path.join(folder, SUMMARY_FILE), SUMMARY_COLUMNS)
    if frame.empty:
        return frame
    for column in ('ic', 'budget', 'n_runs', 'near_count'):
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    return frame.dropna(subset=['ic', 'budget', 'n_runs', 'near_count']).reset_index(drop=True)


def with_wilson(near: int, n: int) -> Dict:
    """Near-recovery count, rate and the 95% Wilson interval."""
    low, high = wilson_interval(near, n)
    return {'near_count': near, 'n_runs': n, 'rate': near / n if n else float('nan'), 'low': low, 'high': high}


def near_rows(summary: pd.DataFrame, config: str = DETECTION_CONFIG, budget: int = DETECTION_BUDGET) -> List[Dict]:
    """Per (A, target IC) of one configuration at one budget: near counts with Wilson intervals, ordered A then IC."""
    if summary.empty:
        return []
    part = summary[(summary['config'] == config) & (summary['budget'] == budget)].sort_values(['a', 'ic'])
    return [dict(with_wilson(int(r.near_count), int(r.n_runs)), a=str(r.a), ic=float(r.ic)) for r in part.itertuples()]


def near_chart(rows: List[Dict]) -> Dict[str, List[List[Optional[float]]]]:
    """{A: [[IC, rate, low, high]]}; non-finite values become None."""
    def clean(v):
        return None if v is None or not math.isfinite(v) else float(v)
    chart: Dict[str, List[List[Optional[float]]]] = {}
    for r in rows:
        chart.setdefault(r['a'], []).append([clean(r['ic']), clean(r['rate']), clean(r['low']), clean(r['high'])])
    return chart


def read_runs(folder: str) -> pd.DataFrame:
    """Cells of runs.csv (config, ic, formula, seed); empty frame when missing."""
    frame = read_table(os.path.join(folder, RUNS_FILE), ('ic', 'seed'))
    if frame.empty:
        return frame
    for column in ('ic', 'seed'):
        frame[column] = pd.to_numeric(frame[column], errors='coerce')
    return frame.dropna(subset=['ic', 'seed']).reset_index(drop=True)


def seeds_per_cell(summary: pd.DataFrame, config: str = DETECTION_CONFIG) -> Optional[int]:
    """Seeds behind one cell of summary.csv for `config` (the largest `n_runs`); None when there is no such cell."""
    if summary.empty:
        return None
    part = summary[summary['config'] == config]
    return None if part.empty else int(part['n_runs'].max())


def present_values(runs: pd.DataFrame, column: str) -> List[float]:
    """Sorted distinct values of `column` in runs.csv."""
    if runs.empty or column not in runs.columns:
        return []
    return sorted(float(v) for v in pd.to_numeric(runs[column], errors='coerce').dropna().unique())


def near_rows_with_p(rows: List[Dict]) -> List[Dict]:
    """
    Adds `p_fisher` to every row: the one-sided Fisher p against the IC 0 row of the same A (None for IC 0
    itself, NaN when the A has no IC 0 row).
    """
    base = {r['a']: r for r in rows if r['ic'] == 0.0}
    out = []
    for r in rows:
        if r['ic'] == 0.0:
            p = None
        elif r['a'] not in base:
            p = float('nan')
        else:
            p = fisher_p_greater(r['near_count'], r['n_runs'], base[r['a']]['near_count'], base[r['a']]['n_runs'])
        out.append(dict(r, p_fisher=p))
    return out
