"""
WalkForward
===========
Walk-forward test of the LLM + MCTS configuration on real 60m data: for each of 7 windows the
search sees only data before the window (train), the top candidates are re-ranked on the 12 months
before the evaluation segment (validation), and the top-5 trade the next 6 months (evaluation).
The concatenated daily evaluation returns are the out-of-sample series.

Steps (`main.py walkforward <step>`):
    placebo   run the pipeline on K return-permuted copies of the data (no frozen config needed)
    freeze    write frozen.json from the current configuration
    real      run on the real data; refuses unless frozen.json equals the current configuration
    summary   annualised Sharpe of the concatenated evaluation returns per mode and the placebo p-value, and the
              Sharpe difference of every other configuration against llm_mcts (paired stationary block bootstrap)

Per-window pipeline (same functions as the planted-signal runner): a search on the train segment with
reward mode `sharpe`, the distinct leaderboard expressions (at most MAX_RANKED) re-scored on
validation, top-5 by validation reward, equal-weight positions traded on the evaluation segment
with the indicator history taken from the continuous frame. The search is one of `WF_SYSTEMS`:
`llm_mcts` (frozen blueprints, then one feedback round; the default), `mcts_only`, `random`
(`SearchConfigs`, one budget of `BudgetPlan.total` per window) or `oneshot` (every blueprint in turn for
`iterations` each, no feedback) or `llm_only` (the frozen set of complete LLM formulas scored over the template
grid, `LLMOnly`). Two reference strategies skip the search: `buy_hold` and `tsmom` (`Baselines`). Systems without any
randomness (`llm_only`, `buy_hold`, `tsmom`) run with seed 1 only.

Placebo seeds: the permutation seed of placebo set k (1-based) in window w (1..99) is
`PLACEBO_SEED_BASE + 100 * k + w`, i.e. at least 100101. Real runs use MCTS seeds 1-5 and the
planted calibration uses 1001-1020, so the ranges never meet. A placebo run uses MCTS seed 1.
"""

import argparse
import hashlib
import json
import multiprocessing
import os
import subprocess
import sys
import time
import warnings
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core_engine.BacktestEngine import AlphaBacktestEngine, load_data
from strategy_workflows.Baselines import (
    POSITION_SCALE, TSMOM_LOOKBACK_SESSIONS, bars_per_session, buy_hold_positions, tsmom_lookbacks, tsmom_positions,
)
from strategy_workflows.LLMOnly import load_formula_set, score_formulas, template_grid, window_ladders
from strategy_workflows.MCTSEngine import MCTSEngine, _FixedPositions
from strategy_workflows.PlantedSignal import (
    TOP_K, Segments, build_ohlcv_from_returns, combine_positions, permute_returns, split_bars,
)
from strategy_workflows.RunPlantedSignal import (
    MAX_RANKED, TIMEFRAME, candidate_positions, load_blueprints, quiet, rank_leaderboard,
)
from strategy_workflows.SearchConfigs import (
    SYSTEMS, BudgetPlan, create_worker_chat, feedback_records, feedback_summary_lines, llm_spec, run_search,
    summarize_feedback,
)
from strategy_workflows.SemanticCompiler import SemanticCompiler
from strategy_workflows.Statistics import paired_sharpe_bootstrap
from utilities.AppConfig import MCTS_MAX_DEPTH, REWARD_WEIGHTS

REWARD_MODE = 'sharpe'
DEFAULT_SYSTEM = 'llm_mcts'
# Systems whose result cannot depend on the seed (no sampling anywhere): one run each.
DETERMINISTIC_SYSTEMS = ('llm_only', 'buy_hold', 'tsmom')
REFERENCE_SYSTEMS = ('buy_hold', 'tsmom')
DETERMINISTIC_SEEDS = [1]
WF_SYSTEMS = SYSTEMS + ('oneshot',) + DETERMINISTIC_SYSTEMS
COMPARISON_REFERENCE = 'llm_mcts'
DEFAULT_BLUEPRINTS = os.path.join(PROJECT_ROOT, 'results', 'blueprint_sets', '20261029_212813', 'blueprints.json')
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, 'results', 'walkforward')
DEFAULT_ITERATIONS = 5000
DEFAULT_BLUEPRINT_COUNT = 20
DEFAULT_SEEDS = [1, 2, 3, 4, 5]
DEFAULT_PLACEBO_SETS = 19
PLACEBO_MCTS_SEED = 1
PLACEBO_SEED_BASE = 100000
FIRST_EVAL_START = '2022-07-01'
N_WINDOWS = 7
VALIDATION_MONTHS = 12
EVAL_MONTHS = 6
TRADING_DAYS_PER_YEAR = 252
# Tracked code whose difference from the frozen commit invalidates a frozen configuration.
CODE_PATHS = ['main.py', 'core_engine', 'strategy_workflows', 'utilities']

RUN_KEY = ['mode', 'placebo_set', 'window', 'seed']
RUN_FIELDS = RUN_KEY + [
    'data_seed', 'iterations', 'n_blueprints', 'blueprint_errors', 'evaluations', 'failed', 'top_errors',
    'n_ranked', 'n_top', 'train_best_reward', 'top', 'top_train_rewards', 'top_val_rewards', 'eval_sharpe',
    'eval_trades', 'elapsed_s', 'system', 'llm_s', 'llm_requests', 'new_blueprints', 'feedback', 'info',
]
RETURN_FIELDS = ['date', 'window', 'seed', 'mode', 'placebo_set', 'return']


# --------------------------------------------------------------------------- windows


def wf_plan(total: int = BudgetPlan().total, phase_a: int = BudgetPlan().phase_a,
            chunk: int = BudgetPlan().chunk) -> BudgetPlan:
    """Budget plan of a walk-forward run: only the ranking at the end of the budget is used, so no checkpoints."""
    return BudgetPlan(total=total, phase_a=phase_a, chunk=chunk, checkpoints=())


def build_windows(first_eval_start: str = FIRST_EVAL_START, n_windows: int = N_WINDOWS,
                  search_start: str = '2018-08-13') -> List[Segments]:
    """
    Expanding train from `search_start`; validation = the 12 months before each evaluation segment;
    evaluation = 6 months, shifting by 6 months per window. Boundaries are whole calendar days.
    """
    one_day = pd.Timedelta(days=1)
    windows = []
    for i in range(n_windows):
        eval_start = pd.Timestamp(first_eval_start) + pd.DateOffset(months=EVAL_MONTHS * i)
        validation_start = eval_start - pd.DateOffset(months=VALIDATION_MONTHS)
        eval_end = eval_start + pd.DateOffset(months=EVAL_MONTHS) - one_day
        windows.append(Segments(search_start=search_start,
                                train_end=(validation_start - one_day).strftime('%Y-%m-%d'),
                                search_end=(eval_start - one_day).strftime('%Y-%m-%d'),
                                eval_end=eval_end.strftime('%Y-%m-%d')))
    return windows


WINDOWS = build_windows()


def load_full_frame(windows: Sequence[Segments] = WINDOWS) -> pd.DataFrame:
    """Real 60m OHLCV from the first train start to the last evaluation end."""
    return load_data(TIMEFRAME, start=windows[0].search_start, end=windows[-1].eval_end)


# --------------------------------------------------------------------------- placebo


def placebo_seed(set_index: int, window: int) -> int:
    """Permutation seed of placebo set `set_index` (>= 1) in window `window` (1..99); see module doc."""
    if set_index < 1 or not 1 <= window <= 99:
        raise ValueError(f"placebo set must be >= 1 and window in 1..99, got {set_index}, {window}")
    return PLACEBO_SEED_BASE + 100 * set_index + window


def permute_segments(bars: pd.DataFrame, n_train: int, n_search: int, seed: int) -> pd.DataFrame:
    """
    Shuffle whole bar records (return, Volume, shape) inside train, validation and evaluation
    separately, one generator per call. The first bar keeps its placeholder return.
    """
    rng = np.random.default_rng(seed)
    parts = [
        permute_returns(bars.iloc[:n_train], rng, keep_first=True),
        permute_returns(bars.iloc[n_train:n_search], rng),
        permute_returns(bars.iloc[n_search:], rng),
    ]
    return pd.concat(parts)


def placebo_frame(full: pd.DataFrame, segments: Segments, seed: int) -> pd.DataFrame:
    """OHLCV rebuilt from per-segment permuted bar returns; continuous across the segment boundaries."""
    n_train = len(full.loc[:segments.train_end])
    n_search = len(full.loc[:segments.search_end])
    perm = permute_segments(split_bars(full), n_train, n_search, seed)
    return build_ohlcv_from_returns(perm, perm['ret'].to_numpy(), float(full['Close'].iloc[0]))


# --------------------------------------------------------------------------- evaluation


def daily_returns(result) -> pd.Series:
    """
    Daily return on initial capital: last equity of each calendar day, differenced (the first day
    against the initial capital). Same convention as `compute_metrics`, except that the first day's
    P&L is kept so that concatenated segments lose no day.
    """
    daily = result.equity_curve.dropna().resample('D').last().dropna()
    previous = pd.concat([pd.Series([result.initial_capital]), daily.iloc[:-1].reset_index(drop=True)],
                         ignore_index=True)
    return pd.Series((daily.to_numpy() - previous.to_numpy()) / result.initial_capital, index=daily.index)


def annualised_sharpe(returns: pd.Series) -> float:
    """mean / std (ddof 0) * sqrt(252) of daily returns, as in `compute_metrics`; NaN when flat or empty."""
    values = pd.Series(returns).dropna()
    if len(values) < 2 or values.std(ddof=0) == 0:
        return float('nan')
    return float(values.mean() / values.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))


def filled_frame(full: pd.DataFrame) -> pd.DataFrame:
    """Copy of the frame with a missing Volume read as 0, as the search engine does."""
    frame = full.copy()
    frame['Volume'] = frame['Volume'].fillna(0.0)
    return frame


def trade_positions(positions: pd.Series, frame: pd.DataFrame, index: pd.Index) -> Dict:
    """Target positions (computed on a frame that includes the history) traded on the bars `index`."""
    evaluation = frame.loc[index]
    result = AlphaBacktestEngine().run(_FixedPositions(positions.loc[evaluation.index]), evaluation)
    return {'returns': daily_returns(result), 'trades': int(result.total_trades)}


def trade_top(candidates: List[dict], full: pd.DataFrame, evaluation_index: pd.Index) -> Dict:
    """Equal-weight top-k positions (history from the whole frame) traded on the evaluation bars."""
    frame = filled_frame(full)
    if not candidates:
        days = frame.loc[evaluation_index].index.normalize().unique()
        return {'returns': pd.Series(0.0, index=days), 'trades': 0}
    combined = combine_positions([candidate_positions(c, frame) for c in candidates])
    return trade_positions(combined, frame, evaluation_index)


def describe_top(candidates: List[dict], val_rewards: List[float]) -> str:
    return json.dumps([
        {'expr': c['expr'], 'template': c['template'], 'window': c['window'], 'z_score': c['z_score'],
         'threshold_upper': c['threshold_upper'], 'threshold_lower': c['threshold_lower'],
         'direction': c['direction'], 'train_reward': c['reward'], 'val_reward': v}
        for c, v in zip(candidates, val_rewards)
    ])


def run_key_text(task: Dict) -> str:
    """Identity of a run for seeding the LLM: the same window, seed and data ask the same questions."""
    return f"wf|{task['mode']}|{task.get('placebo_set', 0)}|{task['window']}|{task['seed']}"


def search_oneshot(engine: MCTSEngine, task: Dict, search: pd.DataFrame, segments: Segments) -> Dict:
    """Every blueprint in turn for `iterations` iterations, then the top-5 selection: no feedback, no budget plan."""
    compiler = SemanticCompiler()
    blueprint_errors = 0
    for bp in task['blueprints']:
        try:
            engine.run_search_from_blueprint(compiler.compile_blueprint(bp['macro_blueprint']),
                                             n_iterations=task['iterations'])
        except Exception as exc:
            blueprint_errors += 1
            print(f"blueprint {bp['name']} failed: {exc}")
    return {'picked': rank_leaderboard(engine, search, segments, TOP_K), 'summary': engine.error_summary(),
            'iterations': task['iterations'], 'blueprint_errors': blueprint_errors, 'llm_s': 0.0,
            'llm_requests': 0, 'new_blueprints': [], 'feedback': {}}


def search_with_plan(engine: MCTSEngine, task: Dict, search: pd.DataFrame, segments: Segments) -> Dict:
    """One of `SYSTEMS` under `task['plan']`; the final ranking is the one at the end of the budget."""
    llm = task.get('llm')
    chat = create_worker_chat(llm) if task['system'] == 'llm_mcts' else None
    outcome = run_search(task['system'], engine, search, segments, task['plan'], task['blueprints'],
                         run_key_text(task), chat, (llm or {}).get('model_key', 'ollama-local'))
    return {'picked': outcome.final, 'summary': outcome.error_summary, 'iterations': outcome.iterations,
            'blueprint_errors': outcome.blueprint_errors, 'llm_s': outcome.llm_s,
            'llm_requests': outcome.llm_requests, 'new_blueprints': outcome.new_blueprints,
            'feedback': outcome.feedback}


def search_llm_only(engine: MCTSEngine, task: Dict, search: pd.DataFrame, segments: Segments) -> Dict:
    """
    The frozen LLM formulas scored over the template grid on the train segment (best parameters per formula), then
    the usual top-5 selection. The budget is the number of grid evaluations, recorded as `iterations`.
    """
    scored = score_formulas(engine, task['formulas'])
    return {'picked': rank_leaderboard(engine, search, segments, TOP_K), 'summary': engine.error_summary(),
            'iterations': scored['evaluations'], 'blueprint_errors': scored['rejected'], 'llm_s': 0.0,
            'llm_requests': 0, 'new_blueprints': [], 'feedback': {},
            'info': {'formulas': scored['formulas'], 'rejected': scored['rejected'],
                     'grid_evaluations': scored['evaluations']}}


def choose_lookback(validation_sharpes: Dict[str, float]) -> str:
    """Label with the highest validation Sharpe; a NaN Sharpe loses, a tie goes to the earlier (shorter) label."""
    labels = list(validation_sharpes)
    return max(labels, key=lambda label: (
        -float('inf') if np.isnan(validation_sharpes[label]) else validation_sharpes[label], -labels.index(label)))


def run_reference(task: Dict, full: pd.DataFrame, segments: Segments) -> Dict:
    """
    `buy_hold` or `tsmom` on one window. TSMOM picks its lookback by validation Sharpe (positions from the whole
    continuous frame, traded on the validation bars), then trades the evaluation bars with it.
    """
    frame = filled_frame(full)
    info: Dict = {}
    if task['system'] == 'buy_hold':
        positions = buy_hold_positions(frame.index)
    else:
        bars = tsmom_lookbacks(bars_per_session(frame.loc[:segments.train_end]))
        validation = frame.loc[segments.validation_start:segments.search_end].index
        sharpes = {label: annualised_sharpe(
            trade_positions(tsmom_positions(frame['Close'], n), frame, validation)['returns'])
            for label, n in bars.items()}
        chosen = choose_lookback(sharpes)
        positions = tsmom_positions(frame['Close'], bars[chosen])
        info = {'chosen': chosen, 'lookback_bars': bars[chosen], 'bars_by_label': bars,
                'validation_sharpe': {k: None if np.isnan(v) else v for k, v in sharpes.items()}}
    traded = trade_positions(positions, frame, frame.loc[segments.eval_start:segments.eval_end].index)
    return {'returns': traded['returns'], 'trades': traded['trades'], 'info': info}


def reference_outcome(task: Dict, traded: Dict, started: float) -> Dict:
    """Row and returns of a reference run: nothing was searched, so the search columns are empty."""
    row = {field: 0 for field in RUN_FIELDS}
    row.update(
        mode=task['mode'], placebo_set=task.get('placebo_set', 0), window=task['window'], seed=task['seed'],
        data_seed=task.get('data_seed', 0), top_errors='[]', train_best_reward=float('nan'), top='[]',
        top_train_rewards='[]', top_val_rewards='[]', eval_sharpe=annualised_sharpe(traded['returns']),
        eval_trades=traded['trades'], elapsed_s=time.time() - started, system=task['system'], new_blueprints='[]',
        feedback='{}', info=json.dumps(traded['info']))
    return {'row': row, 'returns': traded['returns']}


def run_window(task: Dict) -> Dict:
    """
    One (window, seed, mode, placebo set). `task['frame']` is the continuous real frame from
    search_start to eval_end. `task['system']` picks the search (`WF_SYSTEMS`; `oneshot` when absent).
    Returns {'row': ..., 'returns': daily evaluation returns}.
    """
    warnings.filterwarnings('ignore')
    started = time.time()
    segments: Segments = task['segments']
    full = task['frame']
    data_seed = task.get('data_seed', 0)
    system = task.get('system', 'oneshot')
    if task['mode'] == 'placebo':
        full = placebo_frame(full, segments, data_seed)
    if system in REFERENCE_SYSTEMS:
        return reference_outcome(task, run_reference(task, full, segments), started)
    search = full.loc[:segments.search_end]
    with quiet():
        engine = MCTSEngine(timeframe=TIMEFRAME, max_depth=MCTS_MAX_DEPTH, global_position_matrix=None,
                            seed=task['seed'], data=full.loc[:segments.train_end], reward_mode=REWARD_MODE)
        found = {'oneshot': search_oneshot, 'llm_only': search_llm_only}.get(system, search_with_plan)(
            engine, task, search, segments)
        picked, summary = found['picked'], found['summary']
        top = [picked['ranked'][i] for i in picked['chosen']]
        top_val = [picked['val_rewards'][i] for i in picked['chosen']]
        traded = trade_top(top, full, full.loc[segments.eval_start:segments.eval_end].index)
    returns = traded['returns']
    row = {
        'mode': task['mode'], 'placebo_set': task.get('placebo_set', 0), 'window': task['window'],
        'seed': task['seed'], 'data_seed': data_seed, 'iterations': found['iterations'],
        'n_blueprints': len(task['blueprints']), 'blueprint_errors': found['blueprint_errors'],
        'evaluations': summary['evaluations'], 'failed': summary['failed_evaluations'],
        'top_errors': json.dumps(summary['top_errors']),
        'n_ranked': len(picked['ranked']), 'n_top': len(top),
        'train_best_reward': picked['ranked'][0]['reward'] if picked['ranked'] else float('nan'),
        'top': describe_top(top, top_val),
        'top_train_rewards': json.dumps([c['reward'] for c in top]), 'top_val_rewards': json.dumps(top_val),
        'eval_sharpe': annualised_sharpe(returns), 'eval_trades': traded['trades'],
        'elapsed_s': time.time() - started, 'system': system, 'llm_s': found['llm_s'],
        'llm_requests': found['llm_requests'], 'new_blueprints': json.dumps(found['new_blueprints']),
        'feedback': json.dumps(found['feedback']), 'info': json.dumps(found.get('info', {})),
    }
    return {'row': row, 'returns': returns}


# --------------------------------------------------------------------------- output and resume


def append_rows(path: str, rows: List[Dict], fields: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.DataFrame(rows, columns=fields).to_csv(path, mode='a', header=not os.path.exists(path), index=False)


def append_run(out_dir: str, window: int, outcome: Dict) -> None:
    """
    Append the daily returns first and the runs.csv row last: the row is the commit marker for
    resume, so a crash in between re-runs the task and the duplicate returns are dropped in `summary`.
    """
    row, returns = outcome['row'], outcome['returns']
    frame = pd.DataFrame({
        'date': returns.index.strftime('%Y-%m-%d'), 'window': window, 'seed': row['seed'], 'mode': row['mode'],
        'placebo_set': row['placebo_set'], 'return': returns.to_numpy(),
    }, columns=RETURN_FIELDS)
    append_rows(os.path.join(out_dir, 'returns.csv'), frame.to_dict('records'), RETURN_FIELDS)
    append_rows(os.path.join(out_dir, 'runs.csv'), [row], RUN_FIELDS)


def completed_keys(out_dir: str) -> set:
    path = os.path.join(out_dir, 'runs.csv')
    if not os.path.exists(path):
        return set()
    runs = pd.read_csv(path, usecols=RUN_KEY)
    return {(m, int(k), int(w), int(s)) for m, k, w, s in runs[RUN_KEY].itertuples(index=False)}


def seeds_for(system: str, seeds: Sequence[int]) -> List[int]:
    """Seeds a system is run with: all of `seeds`, or the single seed 1 for a system that cannot vary with it."""
    return list(DETERMINISTIC_SEEDS) if system in DETERMINISTIC_SYSTEMS else list(seeds)


def build_tasks(mode: str, windows: Sequence[Segments], seeds: Sequence[int], blueprints: List[Dict],
                iterations: int, frame: pd.DataFrame, placebo_sets: int = 0,
                window_numbers: Optional[Sequence[int]] = None, system: str = DEFAULT_SYSTEM,
                plan: Optional[BudgetPlan] = None, llm: Optional[dict] = None,
                formulas: Optional[List[Dict]] = None) -> List[Dict]:
    """
    Tasks for `mode`; `window_numbers` (1-based) restricts to some windows of `windows`. `system` is one of
    `WF_SYSTEMS`; `plan` (budget) and `llm` (see `llm_spec`) are used by the search systems, `formulas` (the frozen
    LLM formula set) by `llm_only`. A system without randomness runs with `DETERMINISTIC_SEEDS` whatever `seeds` is.
    """
    if system not in WF_SYSTEMS:
        raise ValueError(f"system must be one of {WF_SYSTEMS}, got {system!r}")
    numbers = list(window_numbers) if window_numbers else list(range(1, len(windows) + 1))
    tasks = []
    if mode == 'real':
        combos = [(0, w, s) for w in numbers for s in seeds_for(system, seeds)]
    else:
        combos = [(k, w, PLACEBO_MCTS_SEED) for k in range(1, placebo_sets + 1) for w in numbers]
    for k, w, seed in combos:
        segments = windows[w - 1]
        tasks.append({
            'mode': mode, 'placebo_set': k, 'window': w, 'seed': seed, 'segments': segments,
            'data_seed': placebo_seed(k, w) if mode == 'placebo' else 0,
            'iterations': iterations, 'blueprints': blueprints, 'system': system, 'plan': plan or wf_plan(),
            'llm': llm, 'formulas': formulas, 'frame': frame.loc[segments.search_start:segments.eval_end],
        })
    return tasks


def execute(tasks: List[Dict], out_dir: str, workers: int,
            runner: Callable[[Dict], Dict] = run_window) -> int:
    """Run the tasks not yet in runs.csv, appending each result as it finishes. Returns the number run."""
    done = completed_keys(out_dir)
    pending = [t for t in tasks if (t['mode'], t['placebo_set'], t['window'], t['seed']) not in done]
    print(f"[walkforward] {len(pending)} to run, {len(tasks) - len(pending)} already in runs.csv, {workers} worker(s)")

    def finish(task: Dict, outcome: Dict) -> None:
        append_run(out_dir, task['window'], outcome)
        row = outcome['row']
        print(f"[walkforward] {row['mode']} set={row['placebo_set']} window={row['window']} seed={row['seed']} "
              f"done in {row['elapsed_s']:.1f}s | failed={row['failed']}/{row['evaluations']} "
              f"eval_sharpe={row['eval_sharpe']:.2f}")

    if workers <= 1 or len(pending) <= 1:
        for task in pending:
            finish(task, runner(task))
        return len(pending)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(runner, t): t for t in pending}
        for future in as_completed(futures):
            task = futures[future]
            try:
                finish(task, future.result())
            except Exception as exc:
                print(f"[walkforward] {task['mode']} set={task['placebo_set']} window={task['window']} "
                      f"seed={task['seed']} failed: {exc}")
    return len(pending)


# --------------------------------------------------------------------------- freeze


def file_sha256(path: str) -> str:
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def data_fingerprint(frame: pd.DataFrame) -> str:
    """sha256 of the index and OHLCV values (same recipe as `HMMValidation.fingerprint_data`, which
    cannot be imported where hmmlearn is missing)."""
    h = hashlib.sha256()
    h.update(frame.index.asi8.tobytes())
    for col in ('Open', 'High', 'Low', 'Close', 'Volume'):
        h.update(np.ascontiguousarray(frame[col].to_numpy(dtype='float64')).tobytes())
    return h.hexdigest()


def relative_path(path: str) -> str:
    """Path relative to the project root when inside it (portable across checkouts), posix separators."""
    absolute = os.path.abspath(path)
    try:
        inside = os.path.commonpath([absolute, PROJECT_ROOT]) == PROJECT_ROOT
    except ValueError:
        inside = False
    return (os.path.relpath(absolute, PROJECT_ROOT) if inside else absolute).replace(os.sep, '/')


def current_commit() -> str:
    return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=PROJECT_ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()


def changed_code_files(commit: str) -> List[str]:
    """Tracked code files whose content differs between `commit` and the working tree."""
    out = subprocess.run(['git', 'diff', '--name-only', commit, '--'] + CODE_PATHS, cwd=PROJECT_ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def template_grid_sizes() -> Dict[str, int]:
    """Number of template-parameter settings per template, from the grid MCTS offers (what `llm_only` scores)."""
    from strategy_workflows.LLMOnly import parse_formula
    periods, window_search = window_ladders()
    samples = {'NORMALIZED': f"ts_mean(pv_close, {periods[0]})", 'RATIO': f"ts_zscore(pv_close, {periods[0]})",
               'BOOLEAN': 'greater_than(pv_close, pv_open)'}
    return {template: len(template_grid(parse_formula(text, periods).tree, window_search, periods))
            for template, text in samples.items()}


def formula_set_config(formulas_path: Optional[str]) -> Dict:
    """The inputs of the `llm_only` configuration: the formula set (and its generation record) and the grid."""
    periods, window_search = window_ladders()
    generation = os.path.join(os.path.dirname(formulas_path), 'generation.json') if formulas_path else None
    return {
        'formulas_path': relative_path(formulas_path) if formulas_path else None,
        'formulas_sha256': file_sha256(formulas_path) if formulas_path else None,
        'n_formulas': len(load_formula_set(formulas_path)) if formulas_path else 0,
        'formulas_generation_sha256': file_sha256(generation) if generation and os.path.exists(generation) else None,
        'llm_only_grid': {'rolling_windows': periods, 'template_windows': window_search,
                          'sizes': template_grid_sizes() if formulas_path else None},
    }


def reference_config() -> Dict:
    """The inputs of the reference strategies: TSMOM lookbacks and selection rule, and the shared position size."""
    return {'tsmom_grid': {'lookback_sessions': dict(TSMOM_LOOKBACK_SESSIONS), 'selection': 'validation_sharpe',
                           'bars_per_session': 'median over the train segment', 'weighting': 'none'},
            'reference_position_scale': POSITION_SCALE}


def current_config(blueprint_path: str, n_blueprints: int, iterations: int, seeds: Sequence[int],
                   data_sha256: str, windows: Sequence[Segments] = WINDOWS, plan: Optional[BudgetPlan] = None,
                   llm_model: str = 'ollama-local', formulas_path: Optional[str] = None) -> Dict:
    """Everything a frozen configuration pins, except the git commit and the choice of system."""
    blueprints = load_blueprints(blueprint_path)[:n_blueprints]
    return {**formula_set_config(formulas_path), **reference_config(),
            'seeds_by_system': {system: seeds_for(system, seeds) for system in WF_SYSTEMS if system != 'oneshot'},
        'reward_mode': REWARD_MODE, 'reward_weights': dict(REWARD_WEIGHTS),
        'windows': [w.to_dict() for w in windows],
        'blueprints_path': relative_path(blueprint_path), 'blueprints_sha256': file_sha256(blueprint_path),
        'n_blueprints': len(blueprints), 'iterations': int(iterations), 'seeds': [int(s) for s in seeds],
        'timeframe': TIMEFRAME, 'max_ranked': MAX_RANKED, 'top_k': TOP_K, 'mcts_max_depth': MCTS_MAX_DEPTH,
        'data_sha256': data_sha256, 'budget_plan': (plan or wf_plan()).to_dict(), 'llm_model': llm_model,
    }


def verify_frozen(frozen: Dict, current: Dict, changed_files: Callable[[str], List[str]] = changed_code_files
                  ) -> List[str]:
    """
    Reasons the current configuration differs from `frozen` (empty list = identical). Every field of
    `current` must be equal (JSON round-trip), and no tracked code file (CODE_PATHS) may differ
    between the frozen commit and the working tree: commits made after freezing (e.g. frozen.json
    itself) are fine, edits to code are not, committed or not.
    """
    problems = []
    for key, value in current.items():
        if key not in frozen:
            problems.append(f"{key}: missing in frozen.json")
        elif json.loads(json.dumps(value)) != frozen[key]:
            problems.append(f"{key}: frozen {frozen[key]!r} != current {value!r}")
    extra = sorted(set(frozen) - set(current) - {'git_commit'})
    problems.extend(f"{key}: not part of the current configuration" for key in extra)
    commit = frozen.get('git_commit')
    if not commit:
        problems.append('git_commit: missing in frozen.json')
    else:
        changed = changed_files(commit)
        if changed:
            problems.append(f"code changed since frozen commit {commit[:10]}: {', '.join(changed[:10])}")
    return problems


def frozen_path(results_root: str) -> str:
    return os.path.join(results_root, 'frozen.json')


# --------------------------------------------------------------------------- summary


def summarize(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Sharpe of the concatenated evaluation returns: real = average over seeds per day, placebo =
    each set separately. p-value on the real row = (1 + placebo Sharpes >= real) / (K + 1), ties
    count as >=, NaN placebo Sharpes are not counted in K.
    """
    returns = returns.drop_duplicates(subset=['date', 'window', 'seed', 'mode', 'placebo_set'], keep='last')
    rows = []
    real_sharpe = float('nan')
    real = returns[returns['mode'] == 'real']
    if not real.empty:
        series = real.groupby('date')['return'].mean().sort_index()
        real_sharpe = annualised_sharpe(series)
        rows.append({'mode': 'real', 'placebo_set': 0, 'n_days': len(series),
                     'n_windows': int(real['window'].nunique()), 'sharpe': real_sharpe})
    placebo = returns[returns['mode'] == 'placebo']
    for k, part in placebo.groupby('placebo_set'):
        series = part.groupby('date')['return'].mean().sort_index()
        rows.append({'mode': 'placebo', 'placebo_set': int(k), 'n_days': len(series),
                     'n_windows': int(part['window'].nunique()), 'sharpe': annualised_sharpe(series)})
    frame = pd.DataFrame(rows, columns=['mode', 'placebo_set', 'n_days', 'n_windows', 'sharpe'])
    frame['p_value'] = np.nan
    if not real.empty and not np.isnan(real_sharpe):
        sharpes = frame.loc[frame['mode'] == 'placebo', 'sharpe'].dropna()
        frame.loc[frame['mode'] == 'real', 'p_value'] = (1 + int((sharpes >= real_sharpe).sum())) / (len(sharpes) + 1)
    return frame


# --------------------------------------------------------------------------- steps


def out_dir_of(args) -> str:
    return os.path.join(args.results_root, args.config or args.system)


def worker_count(args) -> int:
    return args.workers if args.workers else max(1, multiprocessing.cpu_count() - 2)


def plan_from_args(args) -> BudgetPlan:
    return wf_plan(args.total_budget, args.phase_a, args.chunk)


def llm_from_args(args) -> Optional[dict]:
    """Start (or reach) the Ollama model once in the parent; workers attach to it. None for systems without LLM."""
    if args.system != 'llm_mcts':
        return None
    from strategy_workflows.BlueprintGeneration import create_chat
    return llm_spec(create_chat(args.model), args.model)


def step_placebo(args) -> None:
    blueprints = load_blueprints(args.blueprints)[:args.n_blueprints]
    frame = load_full_frame()
    tasks = build_tasks('placebo', WINDOWS, [PLACEBO_MCTS_SEED], blueprints, args.iterations, frame,
                        placebo_sets=args.sets, window_numbers=args.windows, system=args.system,
                        plan=plan_from_args(args), llm=llm_from_args(args), formulas=formulas_for(args))
    execute(tasks, out_dir_of(args), worker_count(args))


def config_from_args(args, frame: pd.DataFrame, formulas_path: Optional[str]) -> Dict:
    return current_config(args.blueprints, args.n_blueprints, args.iterations, args.seeds, data_fingerprint(frame),
                          plan=plan_from_args(args), llm_model=args.model, formulas_path=formulas_path)


def formulas_for(args, frozen: Optional[Dict] = None) -> Optional[List[Dict]]:
    """The LLM formula set of an `llm_only` run (`--formulas`, else the path the frozen record names); else None."""
    if args.system != 'llm_only':
        return None
    path = args.formulas or (frozen or {}).get('formulas_path')
    if not path:
        raise SystemExit("[walkforward] llm_only needs --formulas (the formula set built by `llmonly build`).")
    return load_formula_set(path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path))


def step_freeze(args) -> None:
    if not args.formulas:
        raise SystemExit("[walkforward] freeze pins the LLM-only formula set: pass --formulas "
                         "(the formulas.json built by `llmonly build`).")
    frame = load_full_frame()
    record = {**config_from_args(args, frame, args.formulas), 'git_commit': current_commit()}
    path = frozen_path(args.results_root)
    os.makedirs(args.results_root, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2)
    print(f"[walkforward] Wrote {path}; commit it before running the real step")


def step_real(args) -> None:
    path = frozen_path(args.results_root)
    if not os.path.exists(path):
        raise SystemExit(f"[walkforward] {path} not found; run the freeze step first.")
    with open(path, 'r', encoding='utf-8') as f:
        frozen = json.load(f)
    frame = load_full_frame()
    formulas_path = args.formulas or frozen.get('formulas_path')
    if formulas_path and not os.path.isabs(formulas_path):
        formulas_path = os.path.join(PROJECT_ROOT, formulas_path)
    problems = verify_frozen(frozen, config_from_args(args, frame, formulas_path))
    if problems:
        raise SystemExit("[walkforward] The current configuration differs from frozen.json:\n  "
                         + '\n  '.join(problems))
    blueprints = load_blueprints(args.blueprints)[:args.n_blueprints]
    tasks = build_tasks('real', WINDOWS, args.seeds, blueprints, args.iterations, frame, system=args.system,
                        plan=plan_from_args(args), llm=llm_from_args(args), formulas=formulas_for(args, frozen))
    execute(tasks, out_dir_of(args), worker_count(args))


COMPARISON_FIELDS = ['config', 'n_days', 'sharpe_reference', 'sharpe_config', 'difference', 'ci_low', 'ci_high', 'rho']


def real_daily_series(returns: pd.DataFrame) -> pd.Series:
    """Evaluation returns of the real runs, averaged over seeds per day (a repeated row counts once)."""
    returns = returns.drop_duplicates(subset=['date', 'window', 'seed', 'mode', 'placebo_set'], keep='last')
    return returns[returns['mode'] == 'real'].groupby('date')['return'].mean().sort_index()


def compare_configs(series: Dict[str, pd.Series], reference: str = COMPARISON_REFERENCE) -> pd.DataFrame:
    """
    Per configuration other than `reference`: Sharpe of both on their common days, `difference` = Sharpe(reference)
    - Sharpe(config) with its 95% interval from the paired stationary block bootstrap, and the daily-return
    correlation rho. Positive means the reference is better.
    """
    rows = []
    for name, other in series.items():
        if name == reference or reference not in series:
            continue
        joined = pd.concat([series[reference].rename('reference'), other.rename('config')], axis=1, join='inner').dropna()
        if len(joined) < 2:
            continue
        stats = paired_sharpe_bootstrap(joined['reference'].to_numpy(), joined['config'].to_numpy())
        rows.append({'config': name, 'n_days': stats['n_days'], 'sharpe_reference': annualised_sharpe(joined['reference']),
                     'sharpe_config': annualised_sharpe(joined['config']), 'difference': stats['difference'],
                     'ci_low': stats['ci_low'], 'ci_high': stats['ci_high'], 'rho': stats['rho']})
    return pd.DataFrame(rows, columns=COMPARISON_FIELDS)


def step_compare(args) -> None:
    """Write and print `comparison.csv` for every configuration folder of the results root that has real returns."""
    series = {}
    for name in sorted(os.listdir(args.results_root)) if os.path.isdir(args.results_root) else []:
        path = os.path.join(args.results_root, name, 'returns.csv')
        if os.path.exists(path):
            daily = real_daily_series(pd.read_csv(path))
            if not daily.empty:
                series[name] = daily
    if COMPARISON_REFERENCE not in series:
        print(f"[walkforward] No real {COMPARISON_REFERENCE} returns under {args.results_root}; no comparison.")
        return
    comparison = compare_configs(series)
    out = os.path.join(args.results_root, 'comparison.csv')
    comparison.to_csv(out, index=False)
    print(f"[walkforward] Sharpe({COMPARISON_REFERENCE}) minus Sharpe(config), 95% CI of the paired stationary block "
          "bootstrap")
    with pd.option_context('display.width', 200, 'display.max_columns', None):
        print(comparison.round(4).to_string(index=False))
    print(f"[walkforward] Wrote {out}")


def step_summary(args) -> None:
    path = os.path.join(out_dir_of(args), 'returns.csv')
    if not os.path.exists(path):
        print(f"[walkforward] {path} not found; run the placebo or real step first.")
        return
    summary = summarize(pd.read_csv(path))
    out = os.path.join(out_dir_of(args), 'summary.csv')
    summary.to_csv(out, index=False)
    with pd.option_context('display.width', 200, 'display.max_columns', None):
        print(summary.round(4).to_string(index=False))
    print(f"[walkforward] Wrote {out}")
    runs_path = os.path.join(out_dir_of(args), 'runs.csv')
    if os.path.exists(runs_path):
        runs = pd.read_csv(runs_path)
        for line in feedback_summary_lines(summarize_feedback(feedback_records(runs, RUN_KEY)), '[walkforward]'):
            print(line)
    step_compare(args)


# --------------------------------------------------------------------------- CLI


def add_walkforward_parser(subparsers) -> None:
    parser = subparsers.add_parser('walkforward', help='Walk-forward test (LLM + MCTS)')
    steps = parser.add_subparsers(dest='step', required=True)

    def common(p, run_options=True):
        p.add_argument('--system', default=DEFAULT_SYSTEM, choices=list(WF_SYSTEMS),
                       help='Search: llm_mcts (frozen blueprints + feedback round), mcts_only, random, oneshot '
                            '(every blueprint in turn, no feedback), llm_only (frozen LLM formulas), or the '
                            'references buy_hold and tsmom')
        p.add_argument('--config', default=None, help='Folder name under the results root (default: the system)')
        p.add_argument('--results-root', default=DEFAULT_RESULTS_ROOT)
        if run_options:
            p.add_argument('--blueprints', default=DEFAULT_BLUEPRINTS)
            p.add_argument('--formulas', default=None,
                           help='Frozen LLM formula set (llm_only; required by freeze, taken from frozen.json by real)')
            p.add_argument('--n-blueprints', type=int, default=DEFAULT_BLUEPRINT_COUNT,
                           help='Use the first N blueprints of the file')
            p.add_argument('--iterations', type=int, default=DEFAULT_ITERATIONS,
                           help='Iterations per blueprint (oneshot only)')
            p.add_argument('--total-budget', type=int, default=BudgetPlan().total,
                           help='Iterations (random: samples) per window and seed, all systems but oneshot')
            p.add_argument('--phase-a', type=int, default=BudgetPlan().phase_a,
                           help='Share of the budget for the frozen blueprints before the feedback round (llm_mcts)')
            p.add_argument('--chunk', type=int, default=BudgetPlan().chunk, help='Iterations per blueprint per pass')
            p.add_argument('--model', default='ollama-local', choices=['ollama-local', 'ollama-9b'],
                           help='LLM of the feedback round (llm_mcts)')
            p.add_argument('--workers', type=int, default=0, help='Worker processes (default: cpu_count - 2)')

    p = steps.add_parser('placebo', help='Run on permuted-return copies of the data')
    common(p)
    p.add_argument('--sets', type=int, default=DEFAULT_PLACEBO_SETS, help='Number of placebo sets K')
    p.add_argument('--windows', type=int, nargs='+', default=None, help='Window numbers 1-7 (default: all)')

    p = steps.add_parser('freeze', help='Write frozen.json from the current configuration')
    common(p)
    p.add_argument('--seeds', type=int, nargs='+', default=DEFAULT_SEEDS)

    p = steps.add_parser('real', help='Run on real data; needs a matching frozen.json')
    common(p)
    p.add_argument('--seeds', type=int, nargs='+', default=DEFAULT_SEEDS)

    p = steps.add_parser('summary', help='Sharpe of the concatenated evaluation returns and the placebo p-value')
    common(p, run_options=False)


def run_walkforward(args) -> None:
    {'placebo': step_placebo, 'freeze': step_freeze, 'real': step_real, 'summary': step_summary}[args.step](args)
