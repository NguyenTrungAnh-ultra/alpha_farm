"""
RunPlantedSignal
================
Planted-signal test: does the pipeline (frozen blueprints -> MCTS -> top-5 portfolio) find a
formula that is known to be in the data, and is it quiet when nothing is there?

Steps (`main.py planted <step>`):
    blueprints  generate and freeze the blueprint set
    select      derive the planted formula from the frozen set and store it (planted_formula.json)
    oracle      score the planted formula itself on each planted frame (no search)
    search      run MCTS per (strength, seed), recover-check and trade the top-5 out of sample
    summary     aggregate runs.csv and print the pass/fail criteria
"""

import argparse
import contextlib
import hashlib
import json
import multiprocessing
import os
import re
import sys
import time
import warnings
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core_engine.AlphaEngine import AlphaDataProxy
from core_engine.BacktestEngine import AlphaBacktestEngine, load_data
from core_engine.CalculateMetrics import compute_metrics
from strategy_workflows.MCTSEngine import (
    MCTSEngine, _FixedPositions, _TemplateStrategy, compute_positions, describe_candidate, evaluate_alpha,
    find_unimplemented_operator,
)
from strategy_workflows.PlantedSignal import (
    TOP_K, Calibration, PlantedData, PlantedFormula, Segments,
    assert_in_search_space, build_planted_data, calibrate_beta, can_express, combine_positions,
    formula_from_dict, formula_to_dict, is_exact_recovery, is_near_recovery, is_verbatim,
    distinct_expressions, rank_by_validation, select_planted_formula, spearman_abs,
)
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler
from utilities.AppConfig import MCTS_MAX_DEPTH, REWARD_MODES

TIMEFRAME = '60m'
# The search segment is split (see Segments): MCTS sees only bars up to train_end; the leaderboard is then
# ranked by reward on validation_start..search_end. The split is configurable per run from the command line
# and stored in <out-dir>/segments.json so one output folder never mixes splits.
MAX_RANKED = 100
DEFAULT_STRENGTHS = [0.0, 0.01, 0.02, 0.05, 0.1, 0.2]
DEFAULT_SEEDS = [1, 2, 3, 4, 5]
DEFAULT_ITERATIONS = 5000
DEFAULT_BLUEPRINT_COUNT = 20
Z_THRESHOLDS = [0.5, 1.0, 1.5, 2.0, 2.5]

RUN_KEY = ['reward_mode', 'strength', 'seed', 'iterations']
RUN_FIELDS = RUN_KEY + [
    'n_blueprints', 'blueprint_errors', 'beta', 'ic_search', 'ic_eval', 'evaluations', 'failed', 'gated',
    'gate_rate', 'stop_reasons', 'n_ranked', 'n_top', 'train_best_reward', 'best_expr', 'top_exprs',
    'top_val_rewards', 'top_train_ranks', 'closest_expr', 'closest_corr', 'closest_train_rank',
    'closest_val_rank', 'closest_val_reward', 'exact', 'near', 'best_corr', 'oos_sharpe', 'oos_trades',
    'elapsed_s',
]
ORACLE_FIELDS = [
    'strength', 'seed', 'beta', 'ic_search', 'ic_eval', 'reward_gated', 'reward_soft', 'z_gated', 'z_soft',
    'calmar', 'trades', 'rank_ic', 'reward_soft_train', 'reward_soft_val',
    'reward_sharpe', 'z_sharpe', 'reward_sharpe_train', 'reward_sharpe_val',
]


# --------------------------------------------------------------------------- helpers


def default_out_dir() -> str:
    return os.path.join(PROJECT_ROOT, 'results', 'planted')


def load_base(segments: Segments) -> pd.DataFrame:
    """Real 60m OHLCV covering the search and evaluation segments."""
    return load_data(TIMEFRAME, start=segments.search_start, end=segments.eval_end)


def segments_path(out_dir: str) -> str:
    return os.path.join(out_dir, 'segments.json')


def ensure_segments(out_dir: str, segments: Segments, force: bool = False) -> None:
    """
    Record the segments of this output folder on first use; refuse a different split afterwards
    (runs.csv / oracle.csv rows are only comparable within one split). `force` overwrites the record.
    """
    path = segments_path(out_dir)
    if os.path.exists(path) and not force:
        with open(path, 'r', encoding='utf-8') as f:
            stored = Segments.from_dict(json.load(f))
        if stored != segments:
            raise SystemExit(f"[planted] {path} holds {stored.to_dict()} but {segments.to_dict()} was requested; "
                             f"use another --out-dir (or --force to overwrite the record).")
        return
    os.makedirs(out_dir, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(segments.to_dict(), f, indent=2)


def segments_from_args(args) -> Segments:
    return Segments(search_start=args.search_start, train_end=args.train_end,
                    search_end=args.search_end, eval_end=args.eval_end)


def load_blueprints(path: str) -> List[Dict[str, str]]:
    with open(path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    return [{'name': i['name'], 'macro_blueprint': i['macro_blueprint']} for i in items]


def formula_path(out_dir: str) -> str:
    return os.path.join(out_dir, 'planted_formula.json')


def load_formula(out_dir: str, path: Optional[str] = None) -> PlantedFormula:
    """The formula stored by the `select` step (or the file given in `path`); refuses to continue without it."""
    path = path or formula_path(out_dir)
    if not os.path.exists(path):
        raise SystemExit(f"[planted] {path} not found; run the select step first.")
    with open(path, 'r', encoding='utf-8') as f:
        return formula_from_dict(json.load(f))


def calibration_key(base: pd.DataFrame, strength: float, formula: PlantedFormula,
                    segments: Segments = Segments()) -> str:
    """Cache key: strength, formula (expression and z-score window) and the data window (bounds, size, price checksum)."""
    checksum = hashlib.md5(base['Close'].to_numpy().tobytes()).hexdigest()[:12]
    return (f"strength={strength}|expr={formula.expr}|z_window={formula.z_window}"
            f"|data={base.index[0]}..{base.index[-1]}|n={len(base)}|search_end={segments.search_end}|close={checksum}")


def get_beta(base: pd.DataFrame, strength: float, out_dir: str, formula: PlantedFormula, workers: int = 1,
             segments: Segments = Segments()) -> float:
    """Calibrated beta for `strength`, from calibration.json when cached, else computed and stored."""
    if strength == 0.0:
        return 0.0
    path = os.path.join(out_dir, 'calibration.json')
    cache = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    key = calibration_key(base, strength, formula, segments)
    if key not in cache:
        started = time.time()
        result = calibrate_beta(base, segments.search_end, strength, formula, workers=workers)
        cache[key] = {
            'beta': result.beta, 'target_ic': strength, 'mean_ic': result.mean_ic, 'std_ic': result.std_ic,
            'perm_seeds': result.seeds, 'evaluations': result.iterations,
            'calibration_s': time.time() - started,
        }
        os.makedirs(out_dir, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
        print(f"[planted] calibrated strength {strength}: beta={result.beta:.5f} "
              f"mean IC={result.mean_ic:.4f} in {time.time() - started:.1f}s")
    return float(cache[key]['beta'])


@contextlib.contextmanager
def quiet():
    """Silence the engine's progress printing."""
    with open(os.devnull, 'w', encoding='utf-8') as sink, contextlib.redirect_stdout(sink):
        yield


def normalized_tree(expr: ASTNode, window: int, z_score: float) -> ASTNode:
    return ASTNode(name='normalized_template', children=[
        expr, ASTNode(name='window', value=window), ASTNode(name='z_score', value=z_score),
    ])


# --------------------------------------------------------------------------- step: blueprints


def annotate_blueprints(blueprints: List[Dict[str, str]], formula: PlantedFormula) -> List[Dict]:
    """Add `can_express` and `verbatim` flags (against the planted formula) to each blueprint."""
    compiler = SemanticCompiler()
    target = formula.expr_ast()
    out = []
    for bp in blueprints:
        root = compiler.compile_blueprint(bp['macro_blueprint'])
        out.append({**bp, 'can_express': can_express(root, target), 'verbatim': is_verbatim(root, target)})
    return out


def generate_blueprints(n: int, model: str) -> List[Dict[str, str]]:
    """Ask the local LLM for `n` compilable 60m blueprints (prompt variant "current"); nothing is written to results/ideas."""
    from strategy_workflows.BlueprintGeneration import create_chat, generate_set, load_variant_experience

    chat = create_chat(model)
    try:
        accepted, _ = generate_set(chat, n, 'current', model=model, experience=load_variant_experience('current'))
    finally:
        if hasattr(chat, 'stop_keepalive'):
            chat.stop_keepalive()
    return accepted


def step_blueprints(args) -> None:
    path = args.blueprints or os.path.join(args.out_dir, 'blueprints.json')
    if os.path.exists(path) and not args.force:
        print(f"[planted] {path} already exists; the set is frozen. Use --force to regenerate.")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blueprints = generate_blueprints(args.n, args.model)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(blueprints, f, indent=4, ensure_ascii=False)
    print(f"[planted] Froze {len(blueprints)} blueprints to {path}; run the select step next")


# --------------------------------------------------------------------------- step: select


def step_select(args) -> None:
    path = args.blueprints or os.path.join(args.out_dir, 'blueprints.json')
    blueprints = load_blueprints(path)
    segments = segments_from_args(args)
    ensure_segments(args.out_dir, segments, args.force)
    base = load_base(segments)
    with quiet():
        engine = MCTSEngine(timeframe=TIMEFRAME, data=base.loc[:segments.search_end], global_position_matrix=None)
    formula, info = select_planted_formula(blueprints, engine)
    annotated = annotate_blueprints(blueprints, formula)
    source = next(b for b in annotated if b['name'] == formula.source)
    if not source['can_express']:
        raise RuntimeError(f"Selected blueprint {formula.source} cannot express its own formula")
    expressing = [b['name'] for b in annotated if b['can_express']]
    record = {**formula_to_dict(formula), 'window_choice': info, 'blueprints_file': os.path.basename(path),
              'n_blueprints': len(blueprints), 'expressing_blueprints': expressing}
    os.makedirs(args.out_dir, exist_ok=True)
    with open(formula_path(args.out_dir), 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    print(f"[planted] Planted formula: ts_zscore({formula.expr}, {formula.z_window}) under NORMALIZED")
    print(f"[planted] From blueprint {formula.source}: {next(b['macro_blueprint'] for b in blueprints if b['name'] == formula.source)}")
    print(f"[planted] Windows used: period {info['period']}, z-score {info['z_window']}"
          f"{' (ADJUSTED from 10: not in the scaled ladders)' if info['adjusted'] else ''}")
    if info['skipped_verbatim']:
        print(f"[planted] Skipped (filled formula spelled out by a blueprint): {info['skipped_verbatim']}")
    if info['skipped_constant']:
        print(f"[planted] Skipped (filled formula constant on synthetic bars): {info['skipped_constant']}")
    print(f"[planted] {len(expressing)} blueprint(s) can express it: {expressing}")
    print(f"[planted] Wrote {formula_path(args.out_dir)}")


# --------------------------------------------------------------------------- step: oracle


def score_planted_formula(engine: MCTSEngine, formula: PlantedFormula) -> Dict:
    """Best (over the z-score thresholds the search offers) reward of the planted formula itself."""
    best = (-float('inf'), None, None, {})
    for z in Z_THRESHOLDS:
        tree = normalized_tree(formula.expr_ast(), formula.z_window, z)
        reward, _, metrics = engine.evaluate_expression(tree)
        if reward > best[0]:
            best = (reward, z, tree, metrics)
    return {'reward': best[0], 'z': best[1], 'metrics': best[3], 'tree': best[2]}


def planted_split_rewards(train_engine: MCTSEngine, formula: PlantedFormula, search: pd.DataFrame,
                          segments: Segments) -> Dict:
    """
    Reward of the planted formula on the train part and on the validation part, in the reward mode of
    `train_engine`. The z-score threshold and direction are the ones that score best on train;
    validation then scores that fixed strategy.
    """
    best = score_planted_formula(train_engine, formula)
    desc = describe_candidate(best['tree'])
    _, direction, _ = train_engine.evaluate_expression(best['tree'])
    candidate = {'expr': desc['expr'], 'template': desc['template'], 'window': desc['window'],
                 'z_score': desc['z_score_threshold'], 'threshold_upper': desc['threshold_upper'],
                 'threshold_lower': desc['threshold_lower'], 'direction': direction}
    return {'train': best['reward'],
            'validation': train_engine.score_on_span(candidate, search, segments.validation_start,
                                                  segments.search_end)}


def step_oracle(args) -> None:
    segments = segments_from_args(args)
    ensure_segments(args.out_dir, segments, args.force)
    formula = load_formula(args.out_dir, args.formula)
    started = time.time()
    base = load_base(segments)
    workers = args.workers if args.workers else max(1, multiprocessing.cpu_count() - 2)
    rows = []
    for strength in args.strengths:
        beta = get_beta(base, strength, args.out_dir, formula, workers, segments)
        for seed in args.seeds:
            data = build_planted_data(base, segments.search_end, strength, seed, beta, formula)
            scored = {}
            for mode in ('gated', 'soft', 'sharpe'):
                with quiet():
                    engine = MCTSEngine(timeframe=TIMEFRAME, data=data.search, seed=seed,
                                        reward_mode=mode, global_position_matrix=None)
                assert_in_search_space(engine, formula)
                scored[mode] = score_planted_formula(engine, formula)
            split = {}
            for mode in ('soft', 'sharpe'):
                with quiet():
                    train_engine = MCTSEngine(timeframe=TIMEFRAME, data=data.search.loc[:segments.train_end],
                                              seed=seed, reward_mode=mode, global_position_matrix=None)
                    split[mode] = planted_split_rewards(train_engine, formula, data.search, segments)
            soft_metrics = scored['soft']['metrics']
            rows.append({
                'strength': strength, 'seed': seed, 'beta': data.beta, 'ic_search': data.ic_search, 'ic_eval': data.ic_eval,
                'reward_gated': scored['gated']['reward'], 'reward_soft': scored['soft']['reward'],
                'z_gated': scored['gated']['z'], 'z_soft': scored['soft']['z'],
                'calmar': soft_metrics.get('calmar_ratio'), 'trades': soft_metrics.get('total_trades'),
                'rank_ic': soft_metrics.get('rank_ic'),
                'reward_soft_train': split['soft']['train'], 'reward_soft_val': split['soft']['validation'],
                'reward_sharpe': scored['sharpe']['reward'], 'z_sharpe': scored['sharpe']['z'],
                'reward_sharpe_train': split['sharpe']['train'], 'reward_sharpe_val': split['sharpe']['validation'],
            })
    frame = pd.DataFrame(rows, columns=ORACLE_FIELDS)
    path = os.path.join(args.out_dir, 'oracle.csv')
    frame.to_csv(path, index=False)
    with pd.option_context('display.width', 200, 'display.max_columns', None):
        print(frame.round(4).to_string(index=False))
    print(f"[planted] Wrote {path} in {time.time() - started:.1f}s")


# --------------------------------------------------------------------------- step: search


def candidate_positions(candidate: dict, full: pd.DataFrame) -> pd.Series:
    """Target positions of a leaderboard candidate over the whole continuous frame."""
    alpha = evaluate_alpha(candidate['expr'], AlphaDataProxy(full))
    return compute_positions(
        candidate['template'], alpha, candidate['direction'], _TemplateStrategy.position_scale,
        candidate['window'], candidate['z_score'], candidate['threshold_upper'], candidate['threshold_lower'],
    )


def rank_leaderboard(engine: MCTSEngine, search: pd.DataFrame, segments: Segments, k: int = TOP_K) -> Dict:
    """
    Distinct expressions of the train leaderboard (at most MAX_RANKED, train-reward order), scored on the
    validation part of `search` (the continuous frame up to search_end), and the best `k` by that score.
    Returns the train-ordered list, validation rewards aligned with it, and the chosen indices.
    """
    ranked = distinct_expressions(engine.get_best_candidates())[:MAX_RANKED]
    rewards = [engine.score_on_span(c, search, segments.validation_start, segments.search_end) for c in ranked]
    return {'ranked': ranked, 'val_rewards': rewards, 'chosen': rank_by_validation(ranked, rewards)[:k]}


def out_of_sample_sharpe(candidates: List[dict], data: PlantedData) -> Dict:
    """Equal-weight top-k positions (history from the whole frame) traded on the evaluation segment."""
    if not candidates:
        return {'sharpe': float('nan'), 'trades': 0}
    full = data.full.copy()
    full['Volume'] = full['Volume'].fillna(0.0)
    combined = combine_positions([candidate_positions(c, full) for c in candidates])
    evaluation = full.loc[data.evaluation.index]
    result = AlphaBacktestEngine().run(_FixedPositions(combined.loc[evaluation.index]), evaluation)
    metrics = compute_metrics(result)
    sharpe = metrics.get('sharpe_ratio')
    return {'sharpe': float('nan') if sharpe is None else float(sharpe), 'trades': int(metrics.get('total_trades', 0))}


def run_single(task: Dict) -> Dict:
    """One (reward_mode, strength, seed) run; returns a row for runs.csv."""
    warnings.filterwarnings('ignore')
    started = time.time()
    mode, strength, seed, iterations = task['reward_mode'], task['strength'], task['seed'], task['iterations']
    blueprints, formula, segments = task['blueprints'], task['formula'], task['segments']
    with quiet():
        data = build_planted_data(load_base(segments), segments.search_end, strength, seed, task['beta'], formula)
        engine = MCTSEngine(timeframe=TIMEFRAME, max_depth=MCTS_MAX_DEPTH, global_position_matrix=None, seed=seed,
                            data=data.search.loc[:segments.train_end], reward_mode=mode)
        assert_in_search_space(engine, formula)
        compiler = SemanticCompiler()
        stop_reasons: Counter = Counter()
        blueprint_errors = 0
        for bp in blueprints:
            try:
                root = compiler.compile_blueprint(bp['macro_blueprint'])
                stop_reasons[engine.run_search_from_blueprint(root, n_iterations=iterations)] += 1
            except Exception as exc:
                blueprint_errors += 1
                print(f"blueprint {bp['name']} failed: {exc}")

        summary = engine.error_summary()
        picked = rank_leaderboard(engine, data.search, segments, TOP_K)
        ranked, val_rewards, chosen = picked['ranked'], picked['val_rewards'], picked['chosen']
        top = [ranked[i] for i in chosen]

        # Recovery is judged on the whole search segment (train + validation), alphas on the continuous frame.
        search_proxy = AlphaDataProxy(data.search)
        planted_alpha = formula.alpha_series(data.search)
        all_corr = [spearman_abs(evaluate_alpha(c['expr'], search_proxy), planted_alpha) for c in ranked]
        correlations = [all_corr[i] for i in chosen]
        closest = int(np.argmax(all_corr)) if ranked else None
        val_order = rank_by_validation(ranked, val_rewards)
        exact = any(is_exact_recovery(c, formula, engine.scaled_periods, engine.scaled_window_search)
                    for c in top)
        near = any(is_near_recovery(r) for r in correlations)
        oos = out_of_sample_sharpe(top, data)

    evaluations = summary['evaluations']
    return {
        'reward_mode': mode, 'strength': strength, 'seed': seed, 'iterations': iterations,
        'n_blueprints': len(blueprints), 'blueprint_errors': blueprint_errors,
        'beta': data.beta, 'ic_search': data.ic_search, 'ic_eval': data.ic_eval,
        'evaluations': evaluations, 'failed': summary['failed_evaluations'], 'gated': summary['gated_evaluations'],
        'gate_rate': summary['gated_evaluations'] / evaluations if evaluations else float('nan'),
        'stop_reasons': json.dumps(dict(stop_reasons)),
        'n_ranked': len(ranked), 'n_top': len(top),
        'train_best_reward': ranked[0]['reward'] if ranked else float('nan'),
        'best_expr': top[0]['expr'] if top else '',
        'top_exprs': json.dumps([c['expr'] for c in top]),
        'top_val_rewards': json.dumps([val_rewards[i] for i in chosen]),
        'top_train_ranks': json.dumps([i + 1 for i in chosen]),
        'closest_expr': ranked[closest]['expr'] if ranked else '',
        'closest_corr': all_corr[closest] if ranked else float('nan'),
        'closest_train_rank': closest + 1 if ranked else float('nan'),
        'closest_val_rank': val_order.index(closest) + 1 if ranked else float('nan'),
        'closest_val_reward': val_rewards[closest] if ranked else float('nan'),
        'exact': bool(exact), 'near': bool(near), 'best_corr': max(correlations) if correlations else float('nan'),
        'oos_sharpe': oos['sharpe'], 'oos_trades': oos['trades'],
        'elapsed_s': time.time() - started,
    }


def append_run(path: str, row: Dict) -> None:
    pd.DataFrame([row], columns=RUN_FIELDS).to_csv(path, mode='a', header=not os.path.exists(path), index=False)


def step_search(args) -> None:
    segments = segments_from_args(args)
    ensure_segments(args.out_dir, segments, args.force)
    formula = load_formula(args.out_dir, args.formula)
    os.makedirs(args.out_dir, exist_ok=True)
    blueprint_path = args.blueprints or os.path.join(args.out_dir, 'blueprints.json')
    blueprints = load_blueprints(blueprint_path)
    runs_path = os.path.join(args.out_dir, 'runs.csv')
    workers = args.workers if args.workers else max(1, multiprocessing.cpu_count() - 2)
    base = load_base(segments)
    betas = {s: get_beta(base, s, args.out_dir, formula, workers, segments) for s in args.strengths}
    tasks = [
        {'reward_mode': args.reward_mode, 'strength': s, 'seed': seed, 'beta': betas[s],
         'iterations': args.iterations, 'blueprints': blueprints, 'formula': formula, 'segments': segments}
        for s in args.strengths for seed in args.seeds
    ]
    print(f"[planted] {len(tasks)} runs, {len(blueprints)} blueprints, {args.iterations} iterations each, {workers} worker(s)")

    def finish(row: Dict) -> None:
        append_run(runs_path, row)
        print(f"[planted] {row['reward_mode']} strength={row['strength']} seed={row['seed']} "
              f"done in {row['elapsed_s']:.1f}s | ic_search={row['ic_search']:.3f} exact={row['exact']} "
              f"near={row['near']} oos_sharpe={row['oos_sharpe']:.2f}")

    if workers == 1 or len(tasks) == 1:
        for task in tasks:
            finish(run_single(task))
        return
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_single, task): task for task in tasks}
        for future in as_completed(futures):
            task = futures[future]
            try:
                finish(future.result())
            except Exception as exc:
                print(f"[planted] run strength={task['strength']} seed={task['seed']} failed: {exc}")


# --------------------------------------------------------------------------- step: summary


def summarize_runs(runs: pd.DataFrame) -> pd.DataFrame:
    """Per (reward_mode, strength): rates and OOS Sharpe; a rerun of the same key replaces the old row."""
    runs = runs.drop_duplicates(subset=RUN_KEY, keep='last')
    grouped = runs.groupby(['reward_mode', 'strength'])
    summary = grouped.agg(
        n_runs=('seed', 'size'),
        ic_search=('ic_search', 'mean'),
        ic_eval=('ic_eval', 'mean'),
        exact_count=('exact', 'sum'),
        near_count=('near', 'sum'),
        oos_sharpe_mean=('oos_sharpe', 'mean'),
        oos_sharpe_std=('oos_sharpe', 'std'),
    ).reset_index()
    summary['exact_rate'] = summary['exact_count'] / summary['n_runs']
    summary['near_rate'] = summary['near_count'] / summary['n_runs']
    return summary


def criteria_report(summary: pd.DataFrame) -> List[str]:
    """Pre-registered: IC 0.05 near-recovery >= 3 of 5 seeds; IC 0 near-recovery <= 1 of 5."""
    lines = []
    for mode in summary['reward_mode'].unique():
        sub = summary[summary['reward_mode'] == mode]
        for strength, label, ok in ((0.05, 'near >= 3', lambda c: c >= 3), (0.0, 'near <= 1', lambda c: c <= 1)):
            row = sub[np.isclose(sub['strength'], strength)]
            if row.empty:
                lines.append(f"{mode} IC {strength}: no runs")
                continue
            count, n = int(row['near_count'].iloc[0]), int(row['n_runs'].iloc[0])
            lines.append(f"{mode} IC {strength}: near {count}/{n} -> {'PASS' if ok(count) else 'FAIL'} (needs {label} of 5)")
    return lines


def step_summary(args) -> None:
    runs_path = os.path.join(args.out_dir, 'runs.csv')
    if not os.path.exists(runs_path):
        print(f"[planted] {runs_path} not found; run the search step first.")
        return
    summary = summarize_runs(pd.read_csv(runs_path))
    path = os.path.join(args.out_dir, 'summary.csv')
    summary.to_csv(path, index=False)
    with pd.option_context('display.width', 200, 'display.max_columns', None):
        print(summary.round(3).to_string(index=False))
    for line in criteria_report(summary):
        print(f"[planted] {line}")
    print(f"[planted] Wrote {path}")


# --------------------------------------------------------------------------- CLI


def add_planted_parser(subparsers) -> None:
    parser = subparsers.add_parser('planted', help='Planted-signal test')
    steps = parser.add_subparsers(dest='step', required=True)

    def segment_options(p):
        defaults = Segments()
        p.add_argument('--search-start', default=defaults.search_start, help='First day of the train segment')
        p.add_argument('--train-end', default=defaults.train_end, help='Last day MCTS sees; validation starts the day after')
        p.add_argument('--search-end', default=defaults.search_end, help='Last day of validation; evaluation starts the day after')
        p.add_argument('--eval-end', default=defaults.eval_end, help='Last day of the evaluation segment')
        p.add_argument('--force', action='store_true', help='Overwrite <out-dir>/segments.json when it differs')

    def common(p, search_options=True):
        p.add_argument('--out-dir', default=default_out_dir(), help='Output folder (default: results/planted)')
        p.add_argument('--blueprints', default=None, help='Frozen blueprint file (default: <out-dir>/blueprints.json)')
        if search_options:
            p.add_argument('--strengths', type=float, nargs='+', default=DEFAULT_STRENGTHS)
            p.add_argument('--seeds', type=int, nargs='+', default=DEFAULT_SEEDS)

    p = steps.add_parser('blueprints', help='Generate and freeze the blueprint set')
    common(p, search_options=False)
    p.add_argument('--n', type=int, default=DEFAULT_BLUEPRINT_COUNT)
    p.add_argument('--model', default='ollama-local', choices=['ollama-local', 'ollama-9b'])
    p.add_argument('--force', action='store_true', help='Overwrite an existing frozen set')

    p = steps.add_parser('select', help='Derive the planted formula from the frozen blueprint set')
    common(p, search_options=False)
    segment_options(p)

    p = steps.add_parser('oracle', help='Score the planted formula itself on each planted frame')
    common(p)
    segment_options(p)
    p.add_argument('--formula', default=None, help='Planted formula file (default: <out-dir>/planted_formula.json)')
    p.add_argument('--workers', type=int, default=0, help='Calibration worker processes (default: cpu_count - 2)')

    p = steps.add_parser('search', help='MCTS per (strength, seed), recovery and out-of-sample Sharpe')
    common(p)
    segment_options(p)
    p.add_argument('--formula', default=None, help='Planted formula file (default: <out-dir>/planted_formula.json)')
    p.add_argument('--reward-mode', required=True, choices=list(REWARD_MODES))
    p.add_argument('--iterations', type=int, default=DEFAULT_ITERATIONS)
    p.add_argument('--workers', type=int, default=0, help='Worker processes (default: cpu_count - 2)')

    p = steps.add_parser('summary', help='Aggregate runs.csv and print the criteria')
    common(p, search_options=False)


def run_planted(args) -> None:
    {'blueprints': step_blueprints, 'select': step_select, 'oracle': step_oracle, 'search': step_search,
     'summary': step_summary}[args.step](args)
