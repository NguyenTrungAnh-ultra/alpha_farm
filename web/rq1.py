"""
Read-only view of the RQ1 results: the primary tests, recovery rate against budget, first touch of A, the blueprint
coverage of A, and the descriptive walk-forward comparison. Files are opened for reading only; missing or
half-written files give empty results (the pages show the pending state).
"""

import math
import os
from typing import Dict, List, Optional

import pandas as pd

from strategy_workflows.RunRQ1 import PRIMARY_IC
from strategy_workflows.RunRQ1 import RUN_KEY
from strategy_workflows.SearchConfigs import SYSTEMS, feedback_records, summarize_feedback
from web.planted import RUNS_FILE, read_json, read_table, with_wilson

PRIMARY_FILE = 'primary_tests.csv'
TOUCH_FILE = 'first_touch.csv'
COVERAGE_FILE = 'coverage.json'
COMPARISON_FILE = 'comparison.csv'
WALKFORWARD_DIR = 'walkforward'
CONFIG_ORDER = SYSTEMS


def _number(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def read_primary(folder: str) -> List[Dict]:
    """The Holm-adjusted tests of primary_tests.csv in file order; p-values are None when undefined."""
    required = ('budget', 'a_type', 'near_llm_mcts', 'n_llm_mcts', 'near_mcts_only', 'n_mcts_only', 'p_two_sided', 'p_holm')
    frame = read_table(os.path.join(folder, PRIMARY_FILE), required)
    rows = []
    for r in frame.to_dict('records'):
        rows.append({'budget': int(r['budget']), 'a_type': str(r['a_type']), 'ic': _number(r.get('ic')),
                     'near_llm_mcts': int(r['near_llm_mcts']), 'n_llm_mcts': int(r['n_llm_mcts']),
                     'near_mcts_only': int(r['near_mcts_only']), 'n_mcts_only': int(r['n_mcts_only']),
                     'p_two_sided': _number(r['p_two_sided']), 'p_holm': _number(r['p_holm'])})
    return rows


def read_first_touch(folder: str) -> List[Dict]:
    """Medians at the first touch of A per configuration x A x IC (first_touch.csv), configurations in CONFIG_ORDER."""
    required = ('config', 'a', 'ic', 'n_runs', 'n_touched', 'median_iterations', 'median_wall_s')
    frame = read_table(os.path.join(folder, TOUCH_FILE), required)
    rows = []
    for r in frame.to_dict('records'):
        rows.append({'config': str(r['config']), 'a': str(r['a']), 'ic': float(r['ic']), 'n_runs': int(r['n_runs']),
                     'n_touched': int(r['n_touched']), 'median_iterations': _number(r['median_iterations']),
                     'median_wall_s': _number(r['median_wall_s']), 'budget': _number(r.get('budget'))})
    order = {name: i for i, name in enumerate(CONFIG_ORDER)}
    return sorted(rows, key=lambda r: (r['a'], r['ic'], order.get(r['config'], len(order)), r['config']))


def budget_series(summary: pd.DataFrame, ic: float = PRIMARY_IC) -> Dict[str, Dict[str, List[List[Optional[float]]]]]:
    """
    {A: {configuration: [[budget, rate, low, high]]}} at target IC `ic`, budgets ascending, configurations in
    CONFIG_ORDER (others after). Wilson interval recomputed from the counts.
    """
    if summary.empty:
        return {}
    part = summary[(summary['ic'] - ic).abs() < 1e-9].sort_values(['a', 'config', 'budget'])
    order = {name: i for i, name in enumerate(CONFIG_ORDER)}
    out: Dict[str, Dict[str, List[List[Optional[float]]]]] = {}
    for r in part.itertuples():
        stats = with_wilson(int(r.near_count), int(r.n_runs))
        point = [float(r.budget)] + [None if not math.isfinite(stats[k]) else float(stats[k]) for k in ('rate', 'low', 'high')]
        out.setdefault(str(r.a), {}).setdefault(str(r.config), []).append(point)
    return {a: dict(sorted(series.items(), key=lambda kv: (order.get(kv[0], len(order)), kv[0])))
            for a, series in sorted(out.items())}


def near_at(summary: pd.DataFrame, config: str, a: str, ic: float, budget: int) -> Optional[Dict]:
    """Near count and runs of one cell of summary.csv, or None when the cell is absent."""
    if summary.empty:
        return None
    part = summary[(summary['config'] == config) & (summary['a'] == a) & ((summary['ic'] - ic).abs() < 1e-9)
                   & (summary['budget'] == budget)]
    if part.empty:
        return None
    return {'near_count': int(part['near_count'].iloc[0]), 'n_runs': int(part['n_runs'].iloc[0])}


def read_coverage(folder: str) -> List[Dict]:
    """
    Whether each A lies in the region of the initial blueprints (coverage.json): the blueprints that can fill in to
    it and the completion count of the smallest of them (None when outside the region).
    """
    data = read_json(os.path.join(folder, COVERAGE_FILE))
    formulas = data.get('formulas') if isinstance(data, dict) else None
    if not isinstance(formulas, dict):
        return []
    rows = []
    for name in sorted(formulas):
        item = formulas[name]
        if not isinstance(item, dict) or 'in_region' not in item:
            continue
        smallest = item.get('smallest') if isinstance(item.get('smallest'), dict) else None
        rows.append({'a': name, 'in_region': bool(item['in_region']),
                     'expressing': [str(b) for b in item.get('expressing') or []],
                     'verbatim': [str(b) for b in item.get('verbatim') or []],
                     'smallest': None if smallest is None else str(smallest.get('name')),
                     'completions': None if smallest is None else int(smallest['completions'])})
    return rows


def read_feedback(folder: str) -> Optional[Dict]:
    """
    Feedback-round statistics of the runs in runs.csv (`SearchConfigs.summarize_feedback`, the numbers `rq1 summary`
    prints); None when runs.csv or its `feedback` column is missing.
    """
    frame = read_table(os.path.join(folder, RUNS_FILE), ('feedback',) + tuple(RUN_KEY))
    return None if frame.empty else summarize_feedback(feedback_records(frame, RUN_KEY))


COMPARISON_COLUMNS = ('config', 'n_days', 'sharpe_reference', 'sharpe_config', 'difference', 'ci_low', 'ci_high', 'rho')


def read_comparison(results_root: str) -> List[Dict]:
    """
    Walk-forward comparison with the reference configuration (`walkforward summary` writes comparison.csv in the
    walk-forward folder of the results root). Empty when the file is missing.
    """
    frame = read_table(os.path.join(results_root, WALKFORWARD_DIR, COMPARISON_FILE), COMPARISON_COLUMNS)
    rows = []
    for r in frame.to_dict('records'):
        rows.append({'config': str(r['config']), 'n_days': int(r['n_days']),
                     **{k: _number(r[k]) for k in COMPARISON_COLUMNS if k not in ('config', 'n_days')}})
    return rows
