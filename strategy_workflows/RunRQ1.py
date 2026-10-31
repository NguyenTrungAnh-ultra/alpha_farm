"""
RunRQ1
======
The planted-signal comparison of the three search configurations (RQ1): does the LLM get MCTS to a planted formula
earlier, or block the way to it? Same planted data, same budget, same top-5 selection; what differs is how the
candidates are produced (`SearchConfigs`).

Steps (`main.py rq1 <step>`):
    formulas   choose A1..A4 (A3 and A4 are random) and write planted_formulas.json; stops when A1 or A2 is
               non-stationary or crowded
    coverage   which blueprints of the frozen set can fill in to each A, and how many completions the smallest has
    search     run every cell, resumable; writes runs.csv and checkpoints.csv
    summary    recovery rates per configuration x A x IC x budget (Wilson intervals, no p), the one primary test
               (llm_mcts vs mcts_only at IC 0.1, pooled by A type, 4 two-sided Fisher tests with Holm), the RQ2
               detection threshold of llm_mcts per A, and first-touch medians

A cell is (configuration, IC, A, seed). IC 0 plants nothing, so its cell is shared by the four A: one run per
(configuration, seed) is scored against every A. Per cell and per checkpoint budget the ranking on the leaderboard
at that moment is judged against A:
    near          some top-5 candidate has |Spearman| >= 0.7 with A (raw alpha values on the search segment)
    best_corr     the largest |Spearman| among the top-5
    closest       the candidate closest to A among all ranked (at most MAX_RANKED) and its |Spearman|
    touched       some leaderboard entry reached |Spearman| >= 0.7 with A, checked after every chunk of the search;
                  the iterations, evaluations and wall seconds at the first chunk where that held
"""

import argparse
import json
import multiprocessing
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core_engine.AlphaEngine import AlphaDataProxy
from core_engine.BacktestEngine import load_data
from strategy_workflows.MCTSEngine import MCTSEngine, evaluate_alpha
from strategy_workflows.PlantedFormulas import (
    ClassicalCheckFailed, coverage_report, formulas_from_dict, formulas_to_dict, select_rq1_formulas,
)
from strategy_workflows.PlantedSignal import (
    NEAR_CORRELATION, PlantedFormula, Segments, assert_in_search_space, build_planted_data, spearman_abs,
)
from strategy_workflows.RunPlantedSignal import (
    TIMEFRAME, ensure_segments, get_beta, load_base, load_blueprints, out_of_sample_sharpe, quiet,
)
from strategy_workflows.SearchConfigs import (
    CHECKPOINTS, SYSTEMS, BudgetPlan, create_worker_chat, llm_spec, run_search,
)
from strategy_workflows.Statistics import detection_threshold, fisher_p_greater, holm_adjust, wilson_interval
from utilities.AppConfig import MCTS_MAX_DEPTH

DEFAULT_OUT_DIR = os.path.join(PROJECT_ROOT, 'results', 'planted_rq1')
DEFAULT_SEEDS = list(range(1, 11))
IC_LEVELS = [0.05, 0.1]
CONDITIONAL_IC = 0.2
FORMULA_NAMES = ['A1', 'A2', 'A3', 'A4']
REWARD_MODE = 'sharpe'
SHARED = ''                    # `formula` value of an IC 0 run, shared by every A

# The one primary comparison and the RQ2 reading, fixed before the runs.
PRIMARY_CONFIGS = ('llm_mcts', 'mcts_only')
PRIMARY_IC = 0.1
PRIMARY_BUDGETS = (50_000, 100_000)
A_TYPES = {'classical': ('A1', 'A2'), 'odd': ('A3', 'A4')}
DETECTION_CONFIG = 'llm_mcts'
DETECTION_BUDGET = 100_000
CHECKPOINT_KEY = ['config', 'ic', 'run_formula', 'seed', 'a', 'budget']

RUN_KEY = ['config', 'ic', 'formula', 'seed']
RUN_FIELDS = RUN_KEY + [
    'beta', 'ic_search', 'ic_eval', 'n_blueprints', 'blueprint_errors', 'iterations', 'evaluations', 'failed',
    'wall_s', 'llm_s', 'llm_requests', 'elapsed_s', 'stop_reasons', 'new_blueprints', 'feedback', 'random_stats',
    'oos_sharpe', 'top_exprs',
]
CHECKPOINT_FIELDS = [
    'config', 'ic', 'run_formula', 'seed', 'a', 'budget', 'iterations', 'evaluations', 'wall_s', 'llm_s', 'n_ranked',
    'near', 'best_corr_top5', 'closest_expr', 'closest_corr', 'touched', 'touch_iterations', 'touch_evaluations',
    'touch_wall_s', 'top_exprs',
]


# --------------------------------------------------------------------------- measurement


class CorrelationTracker:
    """|Spearman| of expressions with one planted alpha on the search segment, each expression computed once."""

    def __init__(self, planted_alpha: pd.Series, search: pd.DataFrame):
        self.planted_alpha = planted_alpha
        self.proxy = AlphaDataProxy(search)
        self._cache: Dict[str, float] = {}

    def __call__(self, expr: str) -> float:
        if expr not in self._cache:
            try:
                self._cache[expr] = spearman_abs(evaluate_alpha(expr, self.proxy), self.planted_alpha)
            except Exception:
                self._cache[expr] = 0.0
        return self._cache[expr]


class TouchWatch:
    """First chunk at which some leaderboard entry reaches |Spearman| >= threshold with A."""

    def __init__(self, tracker: Callable[[str], float], threshold: float = NEAR_CORRELATION):
        self.tracker = tracker
        self.threshold = threshold
        self.first: Optional[dict] = None

    def update(self, engine: MCTSEngine, spent: int, wall_s: float) -> None:
        if self.first is None and any(self.tracker(item['expr']) >= self.threshold for item in engine.leaderboard):
            self.first = {'iterations': spent, 'evaluations': engine.evaluation_count, 'wall_s': wall_s}


def recovery_metrics(picked: dict, tracker: Callable[[str], float], threshold: float = NEAR_CORRELATION) -> dict:
    """
    Recovery of one planted alpha in a ranking: `picked` is the result of `rank_leaderboard` (train-ordered
    `ranked`, indices `chosen` for the top-5). `near`/`best_corr_top5` look at the top-5 only; `closest` at every
    ranked candidate.
    """
    ranked, chosen = picked['ranked'], picked['chosen']
    correlations = [tracker(c['expr']) for c in ranked]
    top = [correlations[i] for i in chosen]
    closest = int(np.argmax(correlations)) if ranked else None
    return {
        'n_ranked': len(ranked),
        'near': bool(any(value >= threshold for value in top)),
        'best_corr_top5': max(top) if top else float('nan'),
        'closest_expr': ranked[closest]['expr'] if ranked else '',
        'closest_corr': correlations[closest] if ranked else float('nan'),
        'top_exprs': json.dumps([ranked[i]['expr'] for i in chosen]),
    }


# --------------------------------------------------------------------------- cells


def task_key(task: dict) -> tuple:
    return (task['config'], round(float(task['ic']), 6), task['formula'], int(task['seed']))


def run_key_text(task: dict) -> str:
    """Identity of a cell for seeding the LLM: the same cell asks the same questions."""
    return f"rq1|{task['config']}|ic={task['ic']}|{task['formula'] or 'shared'}|seed={task['seed']}"


def ic_levels_for(config: str, ics: Sequence[float], include_conditional: bool) -> List[float]:
    """IC levels above 0 of a configuration; the conditional 0.2 level exists for llm_mcts only."""
    levels = list(ics)
    if include_conditional and config == 'llm_mcts' and CONDITIONAL_IC not in levels:
        levels.append(CONDITIONAL_IC)
    return levels


def build_tasks(configs: Sequence[str], formula_names: Sequence[str], ics: Sequence[float], seeds: Sequence[int],
                include_conditional: bool = False) -> List[dict]:
    """Cells to run (without data or settings): IC 0 once per (configuration, seed), IC > 0 per A."""
    tasks = []
    for config in configs:
        for seed in seeds:
            tasks.append({'config': config, 'ic': 0.0, 'formula': SHARED, 'seed': seed})
            for name in formula_names:
                for ic in ic_levels_for(config, ics, include_conditional):
                    tasks.append({'config': config, 'ic': ic, 'formula': name, 'seed': seed})
    return tasks


def run_cell(task: dict) -> dict:
    """
    One cell. Returns {'run': row for runs.csv, 'checkpoints': rows for checkpoints.csv}. The planted data of
    an IC 0 cell does not depend on A, so A1 stands in for the construction and every A is scored on it.
    """
    warnings.filterwarnings('ignore')
    started = time.time()
    config, ic, seed = task['config'], task['ic'], task['seed']
    formulas: Dict[str, PlantedFormula] = task['formulas']
    shared = task['formula'] == SHARED
    measured = list(formulas) if shared else [task['formula']]
    segments: Segments = task['segments']
    plan: BudgetPlan = task['plan']
    with quiet():
        data = build_planted_data(load_base(segments), segments.search_end, ic, seed, task['beta'],
                                  formulas[FORMULA_NAMES[0]] if shared else formulas[task['formula']])
        engine = MCTSEngine(timeframe=TIMEFRAME, max_depth=MCTS_MAX_DEPTH, global_position_matrix=None, seed=seed,
                            data=data.search.loc[:segments.train_end], reward_mode=REWARD_MODE)
        trackers = {name: CorrelationTracker(formulas[name].alpha_series(data.search), data.search)
                    for name in measured}
        watches = {name: TouchWatch(trackers[name]) for name in measured}
        for name in measured:
            assert_in_search_space(engine, formulas[name])
        chat = create_worker_chat(task['llm']) if config == 'llm_mcts' else None

        def on_chunk(eng: MCTSEngine, spent: int, wall_s: float) -> None:
            for watch in watches.values():
                watch.update(eng, spent, wall_s)

        outcome = run_search(config, engine, data.search, segments, plan, task['blueprints'], run_key_text(task),
                             chat, (task.get('llm') or {}).get('model_key', 'ollama-local'), on_chunk)
        final_top = [outcome.final['ranked'][i] for i in outcome.final['chosen']]
        oos = out_of_sample_sharpe(final_top, data)

    checkpoint_rows = []
    for record in outcome.checkpoints:
        for name in measured:
            touch = watches[name].first
            touched = touch is not None and touch['iterations'] <= record['iterations']
            checkpoint_rows.append({
                'config': config, 'ic': ic, 'run_formula': task['formula'], 'seed': seed, 'a': name,
                'budget': record['budget'], 'iterations': record['iterations'], 'evaluations': record['evaluations'],
                'wall_s': record['wall_s'], 'llm_s': record['llm_s'],
                **recovery_metrics(record['picked'], trackers[name]),
                'touched': bool(touched),
                'touch_iterations': touch['iterations'] if touched else float('nan'),
                'touch_evaluations': touch['evaluations'] if touched else float('nan'),
                'touch_wall_s': touch['wall_s'] if touched else float('nan'),
            })
    summary = outcome.error_summary
    run_row = {
        'config': config, 'ic': ic, 'formula': task['formula'], 'seed': seed, 'beta': data.beta,
        'ic_search': float('nan') if shared else data.ic_search, 'ic_eval': float('nan') if shared else data.ic_eval,
        'n_blueprints': len(task['blueprints']), 'blueprint_errors': outcome.blueprint_errors,
        'iterations': outcome.iterations, 'evaluations': outcome.evaluations, 'failed': summary.get('failed_evaluations'),
        'wall_s': outcome.wall_s, 'llm_s': outcome.llm_s, 'llm_requests': outcome.llm_requests,
        'elapsed_s': time.time() - started, 'stop_reasons': json.dumps(outcome.stop_reasons),
        'new_blueprints': json.dumps(outcome.new_blueprints), 'feedback': json.dumps(outcome.feedback),
        'random_stats': json.dumps(outcome.random_stats), 'oos_sharpe': oos['sharpe'],
        'top_exprs': json.dumps([c['expr'] for c in final_top]),
    }
    return {'run': run_row, 'checkpoints': checkpoint_rows}


# --------------------------------------------------------------------------- output and resume


def append_rows(path: str, rows: List[dict], fields: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.DataFrame(rows, columns=fields).to_csv(path, mode='a', header=not os.path.exists(path), index=False)


def append_cell(out_dir: str, result: dict) -> None:
    """Checkpoint rows first, the run row last: the run row is the commit marker for resume."""
    append_rows(os.path.join(out_dir, 'checkpoints.csv'), result['checkpoints'], CHECKPOINT_FIELDS)
    append_rows(os.path.join(out_dir, 'runs.csv'), [result['run']], RUN_FIELDS)


def completed_keys(out_dir: str) -> set:
    path = os.path.join(out_dir, 'runs.csv')
    if not os.path.exists(path):
        return set()
    runs = pd.read_csv(path, usecols=RUN_KEY, dtype={'formula': str}, keep_default_na=False)
    return {(c, round(float(i), 6), f, int(s)) for c, i, f, s in runs[RUN_KEY].itertuples(index=False)}


def execute(tasks: List[dict], out_dir: str, workers: int, runner: Callable[[dict], dict] = run_cell) -> int:
    """Run the cells not yet in runs.csv, appending each result as it finishes. Returns the number run."""
    done = completed_keys(out_dir)
    pending = [t for t in tasks if task_key(t) not in done]
    print(f"[rq1] {len(pending)} to run, {len(tasks) - len(pending)} already in runs.csv, {workers} worker(s)")

    def finish(result: dict) -> None:
        append_cell(out_dir, result)
        row = result['run']
        print(f"[rq1] {row['config']} ic={row['ic']} {row['formula'] or 'shared'} seed={row['seed']} done in "
              f"{row['elapsed_s']:.1f}s (llm {row['llm_s']:.1f}s)")

    if workers <= 1 or len(pending) <= 1:
        for task in pending:
            finish(runner(task))
        return len(pending)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(runner, t): t for t in pending}
        for future in as_completed(futures):
            task = futures[future]
            try:
                finish(future.result())
            except Exception as exc:
                print(f"[rq1] {task['config']} ic={task['ic']} {task['formula'] or 'shared'} seed={task['seed']} "
                      f"failed: {exc}")
    return len(pending)


# --------------------------------------------------------------------------- summary


def latest_checkpoints(checkpoints: pd.DataFrame) -> pd.DataFrame:
    """A rerun of the same cell replaces the old rows."""
    return checkpoints.drop_duplicates(subset=CHECKPOINT_KEY, keep='last')


def summarize_checkpoints(checkpoints: pd.DataFrame) -> pd.DataFrame:
    """
    Per (configuration, IC, A, budget): number of runs, how many are near / touched, their rates with 95% Wilson
    intervals (no p-value), the mean best top-5 |Spearman| and the median iterations to first touch.
    """
    grouped = latest_checkpoints(checkpoints).groupby(['config', 'ic', 'a', 'budget'])
    out = grouped.agg(
        n_runs=('seed', 'size'), near_count=('near', 'sum'), touched_count=('touched', 'sum'),
        mean_best_corr_top5=('best_corr_top5', 'mean'), mean_closest_corr=('closest_corr', 'mean'),
        median_touch_iterations=('touch_iterations', 'median'), median_touch_wall_s=('touch_wall_s', 'median'),
    ).reset_index()
    out['near_rate'] = out['near_count'] / out['n_runs']
    out['touched_rate'] = out['touched_count'] / out['n_runs']
    for name in ('near', 'touched'):
        bounds = [wilson_interval(int(k), int(n)) for k, n in zip(out[f'{name}_count'], out['n_runs'])]
        out[f'{name}_low'] = [low for low, _ in bounds]
        out[f'{name}_high'] = [high for _, high in bounds]
    return out


def near_counts(frame: pd.DataFrame, config: str, ic: float, names: Sequence[str], budget: int) -> Tuple[int, int]:
    """(near recoveries, runs) of `config` at `ic` and `budget`, pooled over the A in `names`."""
    part = frame[(frame['config'] == config) & np.isclose(frame['ic'].astype(float), ic)
                 & frame['a'].isin(names) & (frame['budget'] == budget)]
    return int(part['near'].astype(bool).sum()), len(part)


def fisher_two_sided(near: int, n: int, other_near: int, other_n: int) -> float:
    """Two-sided Fisher exact p of two near-recovery counts (NaN when a group is empty)."""
    if n <= 0 or other_n <= 0:
        return float('nan')
    return float(fisher_exact([[near, n - near], [other_near, other_n - other_near]], alternative='two-sided')[1])


PRIMARY_FIELDS = ['budget', 'a_type', 'ic', 'near_llm_mcts', 'n_llm_mcts', 'near_mcts_only', 'n_mcts_only',
                  'p_two_sided', 'p_holm']


def primary_tests(checkpoints: pd.DataFrame) -> pd.DataFrame:
    """
    The primary comparison: llm_mcts against mcts_only at IC 0.1, near recovery pooled by A type (classical = A1 + A2,
    odd = A3 + A4) at budgets 50,000 and 100,000: four two-sided Fisher exact tests, Holm-adjusted over the family
    (tests with an empty group are not counted in it).
    """
    frame = latest_checkpoints(checkpoints)
    first, second = PRIMARY_CONFIGS
    rows = []
    for budget in PRIMARY_BUDGETS:
        for a_type, names in A_TYPES.items():
            k1, n1 = near_counts(frame, first, PRIMARY_IC, names, budget)
            k2, n2 = near_counts(frame, second, PRIMARY_IC, names, budget)
            rows.append({'budget': budget, 'a_type': a_type, 'ic': PRIMARY_IC, 'near_llm_mcts': k1, 'n_llm_mcts': n1,
                         'near_mcts_only': k2, 'n_mcts_only': n2, 'p_two_sided': fisher_two_sided(k1, n1, k2, n2)})
    valid = [i for i, row in enumerate(rows) if not np.isnan(row['p_two_sided'])]
    adjusted = holm_adjust([rows[i]['p_two_sided'] for i in valid])
    for row in rows:
        row['p_holm'] = float('nan')
    for i, value in zip(valid, adjusted):
        rows[i]['p_holm'] = value
    return pd.DataFrame(rows, columns=PRIMARY_FIELDS)


DETECTION_FIELDS = ['a', 'config', 'budget', 'threshold_ic', 'p_fisher', 'rates']


def detection_thresholds(checkpoints: pd.DataFrame, config: str = DETECTION_CONFIG,
                         budget: int = DETECTION_BUDGET) -> pd.DataFrame:
    """
    RQ2 per A: the lowest target IC > 0 at which `config`'s near-recovery rate at `budget` beats IC 0 in a one-sided
    Fisher test at 0.05 (`Statistics.detection_threshold`, the rule of the web pages). NaN when no level passes.
    """
    frame = latest_checkpoints(checkpoints)
    rows = []
    for name in sorted(frame['a'].unique()):
        part = frame[(frame['config'] == config) & (frame['a'] == name) & (frame['budget'] == budget)]
        levels = []
        for ic in sorted(part['ic'].astype(float).unique()):
            level = part[np.isclose(part['ic'].astype(float), ic)]
            levels.append({'strength': ic, 'near_count': int(level['near'].astype(bool).sum()), 'n_runs': len(level)})
        base = next((r for r in levels if r['strength'] == 0.0), None)
        for r in levels:
            r['p_fisher'] = None if r['strength'] == 0.0 else (
                float('nan') if base is None else
                fisher_p_greater(r['near_count'], r['n_runs'], base['near_count'], base['n_runs']))
        hit = detection_threshold(levels)
        rows.append({'a': name, 'config': config, 'budget': budget,
                     'threshold_ic': float('nan') if hit is None else hit['strength'],
                     'p_fisher': float('nan') if hit is None else hit['p_fisher'],
                     'rates': '; '.join(f"IC {r['strength']:g}: {r['near_count']}/{r['n_runs']}" for r in levels)})
    return pd.DataFrame(rows, columns=DETECTION_FIELDS)


FIRST_TOUCH_FIELDS = ['config', 'a', 'ic', 'budget', 'n_runs', 'n_touched', 'median_iterations', 'median_evaluations',
                      'median_wall_s']


def first_touch_table(checkpoints: pd.DataFrame) -> pd.DataFrame:
    """
    Medians of iterations, evaluations and wall seconds at the first touch of A per configuration x A x IC, over the
    runs that touched it by the last budget (`n_touched` of `n_runs`: a run that never touched is not in the median).
    """
    frame = latest_checkpoints(checkpoints)
    last = frame[frame['budget'] == frame['budget'].max()]
    grouped = last.groupby(['config', 'a', 'ic'])
    out = grouped.agg(
        budget=('budget', 'max'), n_runs=('seed', 'size'), n_touched=('touched', 'sum'),
        median_iterations=('touch_iterations', 'median'), median_evaluations=('touch_evaluations', 'median'),
        median_wall_s=('touch_wall_s', 'median'),
    ).reset_index()
    return out[FIRST_TOUCH_FIELDS]


# --------------------------------------------------------------------------- steps


def formulas_path(out_dir: str) -> str:
    return os.path.join(out_dir, 'planted_formulas.json')


def load_formulas(out_dir: str, path: Optional[str] = None) -> Dict[str, PlantedFormula]:
    path = path or formulas_path(out_dir)
    if not os.path.exists(path):
        raise SystemExit(f"[rq1] {path} not found; run the formulas step first.")
    with open(path, 'r', encoding='utf-8') as f:
        return formulas_from_dict(json.load(f))


def segments_from_args(args) -> Segments:
    return Segments(search_start=args.search_start, train_end=args.train_end,
                    search_end=args.search_end, eval_end=args.eval_end)


def step_formulas(args) -> None:
    path = formulas_path(args.out_dir)
    if os.path.exists(path) and not args.force:
        raise SystemExit(f"[rq1] {path} exists; the formulas are fixed before the blueprint set is regenerated. "
                         "Use --force to overwrite.")
    segments = segments_from_args(args)
    frame = load_data(TIMEFRAME, start=segments.search_start, end=segments.search_end)
    try:
        selected = select_rq1_formulas(frame)
    except ClassicalCheckFailed as exc:
        raise SystemExit(f"[rq1] A1 / A2 fail the stationarity or crowding check, nothing written: {exc}")
    os.makedirs(args.out_dir, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(formulas_to_dict(selected), f, indent=2, ensure_ascii=False)
    for name, (formula, info) in selected.items():
        print(f"[rq1] {name}: ts_zscore({formula.expr}, {formula.z_window}) x sign {formula.sign:+.0f} | {info}")
    print(f"[rq1] Wrote {path}")


def step_coverage(args) -> None:
    formulas = load_formulas(args.out_dir, args.formulas_file)
    blueprints = load_blueprints(args.blueprints)
    report = {name: coverage_report(blueprints, formula) for name, formula in formulas.items()}
    for name, item in report.items():
        smallest = item['smallest']
        print(f"[rq1] {name}: in region={item['in_region']} expressing={item['expressing']} "
              f"verbatim={item['verbatim']} smallest="
              f"{'-' if smallest is None else str(smallest['name']) + ' with ' + format(smallest['completions'], ',') + ' completions'}")
    path = os.path.join(args.out_dir, 'coverage.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'blueprints_file': os.path.basename(args.blueprints), 'formulas': report}, f, indent=2)
    print(f"[rq1] Wrote {path}")


def plan_from_args(args) -> BudgetPlan:
    return BudgetPlan(total=args.total_budget, phase_a=args.phase_a, chunk=args.chunk,
                      checkpoints=tuple(c for c in CHECKPOINTS if c <= args.total_budget))


def step_search(args) -> None:
    segments = segments_from_args(args)
    ensure_segments(args.out_dir, segments, args.force)
    formulas = load_formulas(args.out_dir, args.formulas_file)
    blueprints = load_blueprints(args.blueprints)
    plan = plan_from_args(args)
    workers = args.workers if args.workers else max(1, multiprocessing.cpu_count() - 2)
    llm = None
    if 'llm_mcts' in args.configs:
        from strategy_workflows.BlueprintGeneration import create_chat
        chat = create_chat(args.model)
        llm = llm_spec(chat, args.model)
    base = load_base(segments)
    tasks = build_tasks(args.configs, args.formula_names, args.ics, args.seeds, args.include_ic02)
    betas = {}
    for task in tasks:
        if task['ic'] > 0 and (task['formula'], task['ic']) not in betas:
            betas[(task['formula'], task['ic'])] = get_beta(base, task['ic'], args.out_dir, formulas[task['formula']],
                                                            workers, segments)
    for task in tasks:
        task.update(beta=betas.get((task['formula'], task['ic']), 0.0), formulas=formulas, segments=segments,
                    plan=plan, blueprints=blueprints, llm=llm)
    execute(tasks, args.out_dir, workers)


def step_summary(args) -> None:
    path = os.path.join(args.out_dir, 'checkpoints.csv')
    if not os.path.exists(path):
        print(f"[rq1] {path} not found; run the search step first.")
        return
    checkpoints = pd.read_csv(path, keep_default_na=True, dtype={'run_formula': str})
    tables = [
        ('summary.csv', 'Recovery rates (Wilson intervals; no p-values outside the primary test)',
         summarize_checkpoints(checkpoints)),
        ('primary_tests.csv', 'Primary test: llm_mcts vs mcts_only at IC 0.1, two-sided Fisher, Holm',
         primary_tests(checkpoints)),
        ('detection_thresholds.csv', f"RQ2 detection threshold of {DETECTION_CONFIG} at {DETECTION_BUDGET:,} per A",
         detection_thresholds(checkpoints)),
        ('first_touch.csv', 'First touch of A (medians over the runs that touched it)',
         first_touch_table(checkpoints)),
    ]
    for name, title, table in tables:
        table.to_csv(os.path.join(args.out_dir, name), index=False)
        print(f"[rq1] {title}")
        with pd.option_context('display.width', 220, 'display.max_columns', None):
            print(table.round(3).to_string(index=False))
        print(f"[rq1] Wrote {os.path.join(args.out_dir, name)}")


# --------------------------------------------------------------------------- CLI


def add_rq1_parser(subparsers) -> None:
    parser = subparsers.add_parser('rq1', help='RQ1 planted-signal comparison of LLM + MCTS, MCTS only and random search')
    steps = parser.add_subparsers(dest='step', required=True)
    defaults = Segments()

    def common(p):
        p.add_argument('--out-dir', default=DEFAULT_OUT_DIR, help='Output folder (default: results/planted_rq1)')
        p.add_argument('--formulas-file', default=None, help='Default: <out-dir>/planted_formulas.json')

    def segment_options(p):
        p.add_argument('--search-start', default=defaults.search_start)
        p.add_argument('--train-end', default=defaults.train_end)
        p.add_argument('--search-end', default=defaults.search_end)
        p.add_argument('--eval-end', default=defaults.eval_end)
        p.add_argument('--force', action='store_true')

    p = steps.add_parser('formulas', help='Choose A1..A4 and write planted_formulas.json')
    p.add_argument('--out-dir', default=DEFAULT_OUT_DIR)
    segment_options(p)

    p = steps.add_parser('coverage', help='Which blueprints can fill in to each A, and the completion counts')
    common(p)
    p.add_argument('--blueprints', required=True, help='Frozen initial blueprint set (blueprints.json)')

    p = steps.add_parser('search', help='Run the cells (resumable)')
    common(p)
    segment_options(p)
    p.add_argument('--blueprints', required=True, help='Frozen initial blueprint set (blueprints.json)')
    p.add_argument('--configs', nargs='+', default=list(SYSTEMS), choices=list(SYSTEMS))
    p.add_argument('--formula-names', nargs='+', default=FORMULA_NAMES, choices=FORMULA_NAMES)
    p.add_argument('--ics', type=float, nargs='+', default=IC_LEVELS)
    p.add_argument('--seeds', type=int, nargs='+', default=DEFAULT_SEEDS)
    p.add_argument('--include-ic02', action='store_true',
                   help='Add the conditional IC 0.2 level, for llm_mcts only (add it only when no A is found at IC 0.1)')
    p.add_argument('--model', default='ollama-local', choices=['ollama-local', 'ollama-9b'])
    p.add_argument('--total-budget', type=int, default=BudgetPlan().total)
    p.add_argument('--phase-a', type=int, default=BudgetPlan().phase_a, help='Budget of the initial blueprints (llm_mcts)')
    p.add_argument('--chunk', type=int, default=BudgetPlan().chunk, help='Iterations per blueprint per pass')
    p.add_argument('--workers', type=int, default=0, help='Worker processes (default: cpu_count - 2)')

    p = steps.add_parser('summary', help='Recovery rates per configuration x A x IC x budget')
    common(p)


def run_rq1(args) -> None:
    {'formulas': step_formulas, 'coverage': step_coverage, 'search': step_search,
     'summary': step_summary}[args.step](args)
