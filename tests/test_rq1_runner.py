import argparse
import json

import numpy as np
import pandas as pd
import pytest

from strategy_workflows import PlantedFormulas as pf
from strategy_workflows import RunRQ1 as rq
from strategy_workflows.PlantedSignal import formula_to_dict
from strategy_workflows.SearchConfigs import BudgetPlan
from tests.test_batched_blueprints import batch_reply, skeletons
from tests.test_walk_forward import SMALL, hourly_frame


def candidate(expr, reward=0.5):
    return {'expr': expr, 'reward': reward}


def picked(exprs, chosen):
    return {'ranked': [candidate(e) for e in exprs], 'val_rewards': [0.0] * len(exprs), 'chosen': list(chosen)}


# --- cells and resume -------------------------------------------------------

def test_cell_grid_matches_the_design():
    tasks = rq.build_tasks(['llm_mcts', 'mcts_only', 'random'], rq.FORMULA_NAMES, rq.IC_LEVELS, rq.DEFAULT_SEEDS)
    assert len(tasks) == 3 * 10 * (1 + 4 * 2) == 270
    shared = [t for t in tasks if t['ic'] == 0.0]
    assert len(shared) == 30 and all(t['formula'] == rq.SHARED for t in shared)       # IC 0: once per config and seed
    assert {(t['config'], t['seed']) for t in shared} == {(c, s) for c in ('llm_mcts', 'mcts_only', 'random')
                                                          for s in range(1, 11)}
    assert len({rq.task_key(t) for t in tasks}) == 270
    assert all(t['formula'] != rq.SHARED for t in tasks if t['ic'] > 0)


def test_conditional_ic_level_exists_for_llm_mcts_only_and_only_when_asked():
    configs = ['llm_mcts', 'mcts_only', 'random']
    plain = rq.build_tasks(configs, rq.FORMULA_NAMES, rq.IC_LEVELS, rq.DEFAULT_SEEDS)
    extra = rq.build_tasks(configs, rq.FORMULA_NAMES, rq.IC_LEVELS, rq.DEFAULT_SEEDS, include_conditional=True)
    added = [t for t in extra if rq.task_key(t) not in {rq.task_key(p) for p in plain}]
    assert len(added) == 40 and {t['config'] for t in added} == {'llm_mcts'} and {t['ic'] for t in added} == {0.2}
    assert rq.ic_levels_for('random', [0.05, 0.1], True) == [0.05, 0.1]


def fake_cell(task):
    measured = rq.FORMULA_NAMES if task['formula'] == rq.SHARED else [task['formula']]
    rows = [{'config': task['config'], 'ic': task['ic'], 'run_formula': task['formula'], 'seed': task['seed'],
             'a': a, 'budget': b, 'iterations': b, 'evaluations': b, 'wall_s': 1.0, 'llm_s': 0.0, 'n_ranked': 3,
             'near': task['seed'] % 2 == 0, 'best_corr_top5': 0.5, 'closest_expr': 'x', 'closest_corr': 0.6,
             'touched': False, 'touch_iterations': float('nan'), 'touch_evaluations': float('nan'),
             'touch_wall_s': float('nan'), 'top_exprs': '[]'} for a in measured for b in (10, 20)]
    run = {k: 0 for k in rq.RUN_FIELDS}
    run.update(config=task['config'], ic=task['ic'], formula=task['formula'], seed=task['seed'], elapsed_s=0.0,
               llm_s=0.0)
    return {'run': run, 'checkpoints': rows}


def test_execute_skips_finished_cells_and_writes_shared_cells_for_every_a(tmp_path):
    out = str(tmp_path)
    tasks = rq.build_tasks(['random'], ['A1', 'A2'], [0.1], [1, 2])
    assert len(tasks) == 2 * (1 + 2) == 6
    assert rq.execute(tasks[:2], out, 1, fake_cell) == 2
    assert rq.execute(tasks, out, 1, fake_cell) == 4
    assert rq.execute(tasks, out, 1, fake_cell) == 0
    runs = pd.read_csv(tmp_path / 'runs.csv', dtype={'formula': str}, keep_default_na=False)
    assert len(runs) == 6 and not runs.duplicated(rq.RUN_KEY).any()
    checkpoints = pd.read_csv(tmp_path / 'checkpoints.csv', dtype={'run_formula': str}, keep_default_na=False)
    shared = checkpoints[checkpoints['run_formula'] == '']
    assert set(shared['a']) == {'A1', 'A2', 'A3', 'A4'} and len(shared) == 2 * 4 * 2     # 2 seeds x 4 A x 2 budgets
    assert list(checkpoints.columns) == rq.CHECKPOINT_FIELDS


def test_a_crash_between_the_two_files_reruns_the_cell_and_summary_drops_the_duplicate(tmp_path):
    out = str(tmp_path)
    task = rq.build_tasks(['random'], ['A1'], [0.1], [2])[1]
    result = fake_cell(task)
    rq.append_rows(str(tmp_path / 'checkpoints.csv'), result['checkpoints'], rq.CHECKPOINT_FIELDS)   # run row missing
    assert rq.completed_keys(out) == set()
    assert rq.execute([task], out, 1, fake_cell) == 1
    checkpoints = pd.read_csv(tmp_path / 'checkpoints.csv', dtype={'run_formula': str})
    assert len(checkpoints) == 4
    summary = rq.summarize_checkpoints(checkpoints)
    assert summary['n_runs'].tolist() == [1, 1]


def test_float_ic_in_the_key_survives_the_csv_roundtrip(tmp_path):
    out = str(tmp_path)
    tasks = [t for t in rq.build_tasks(['llm_mcts'], ['A1'], [0.05, 0.1], [1], include_conditional=True)]
    rq.execute(tasks, out, 1, fake_cell)
    assert rq.execute(tasks, out, 1, fake_cell) == 0


# --- metrics ----------------------------------------------------------------

def tracker_from(values):
    return lambda expr: values[expr]


def test_near_recovery_looks_at_the_top_five_only_and_at_the_threshold_inclusively():
    corr = {'a': 0.2, 'b': 0.7, 'c': 0.69, 'far': 0.9}
    metrics = rq.recovery_metrics(picked(['a', 'b', 'c', 'far'], [0, 2]), tracker_from(corr))
    assert metrics['near'] is False and metrics['best_corr_top5'] == pytest.approx(0.69)
    # 'far' is the closest overall but it is not among the chosen top-5
    assert metrics['closest_expr'] == 'far' and metrics['closest_corr'] == pytest.approx(0.9)
    again = rq.recovery_metrics(picked(['a', 'b', 'c', 'far'], [0, 1]), tracker_from(corr))
    assert again['near'] is True and again['best_corr_top5'] == pytest.approx(0.7)
    assert json.loads(again['top_exprs']) == ['a', 'b'] and again['n_ranked'] == 4


def test_empty_ranking_gives_nan_and_no_recovery():
    metrics = rq.recovery_metrics(picked([], []), tracker_from({}))
    assert metrics['near'] is False and np.isnan(metrics['best_corr_top5']) and metrics['closest_expr'] == ''


class FakeEngine:
    def __init__(self):
        self.leaderboard, self.evaluation_count = [], 0


def test_touch_watch_records_the_first_chunk_with_a_correlated_entry_only():
    corr = {'low': 0.1, 'hit': 0.8, 'later': 0.95}
    watch = rq.TouchWatch(tracker_from(corr))
    engine = FakeEngine()
    engine.leaderboard = [{'expr': 'low'}]
    watch.update(engine, 500, 1.0)
    assert watch.first is None
    engine.leaderboard.append({'expr': 'hit'})
    engine.evaluation_count = 321
    watch.update(engine, 1000, 2.5)
    engine.leaderboard.append({'expr': 'later'})
    watch.update(engine, 1500, 3.0)
    assert watch.first == {'iterations': 1000, 'evaluations': 321, 'wall_s': 2.5}


def test_correlation_tracker_caches_and_treats_bad_expressions_as_uncorrelated():
    frame = hourly_frame('2024-01-01', '2024-03-31')
    planted = pf.classical_formulas()['A2'].alpha_series(frame)
    tracker = rq.CorrelationTracker(planted, frame)
    assert tracker('ts_mean((close - open_), 10)') == pytest.approx(1.0)
    assert tracker('ts_mean((close - open_), 9)') > 0.7
    assert tracker('no such thing(') == 0.0
    assert tracker('close') < 0.7
    assert set(tracker._cache) >= {'ts_mean((close - open_), 10)', 'no such thing('}


def test_summary_rates_and_rerun_replacement():
    base = dict(config='random', ic=0.1, run_formula='A1', a='A1', budget=50, near=False, touched=False,
                best_corr_top5=0.4, closest_corr=0.5, touch_iterations=np.nan, touch_wall_s=np.nan)
    rows = [{**base, 'seed': 1, 'near': True, 'touched': True, 'touch_iterations': 100, 'touch_wall_s': 3.0},
            {**base, 'seed': 2}, {**base, 'seed': 3, 'near': True, 'touched': True, 'touch_iterations': 300,
                                  'touch_wall_s': 9.0},
            {**base, 'seed': 2, 'near': True}]           # a rerun of seed 2 replaces the first row
    summary = rq.summarize_checkpoints(pd.DataFrame(rows))
    row = summary.iloc[0]
    assert (row['n_runs'], row['near_count'], row['touched_count']) == (3, 3, 2)
    assert row['near_rate'] == pytest.approx(1.0) and row['touched_rate'] == pytest.approx(2 / 3)
    assert row['median_touch_iterations'] == pytest.approx(200)


# --- one cell, end to end ---------------------------------------------------

@pytest.fixture
def cell_env(monkeypatch):
    frame = hourly_frame()
    monkeypatch.setattr(rq, 'load_base', lambda segments: frame.loc[segments.search_start:segments.eval_end])
    formulas = {name: formula for name, (formula, _) in pf.select_rq1_formulas(frame.loc[:SMALL.search_end]).items()}

    class Chat:
        model, host = 'fake', 'http://fake'

        def __init__(self):
            self.prompts = []

        def send(self, prompt, schema=None, options=None):
            self.prompts.append(prompt)
            return batch_reply(skeletons(16)[8:11], 'New')

    chats = []
    monkeypatch.setattr(rq, 'create_worker_chat', lambda spec: chats.append(Chat()) or chats[-1])
    plan = BudgetPlan(total=60, phase_a=30, chunk=10, checkpoints=(20, 30, 60), feedback_expressions=3,
                      feedback_blueprints=3)
    blueprints = [{'name': f'B{i}', 'macro_blueprint': b} for i, b in enumerate(skeletons(16)[:3])]

    def task(config, ic, formula, seed=1):
        return {'config': config, 'ic': ic, 'formula': formula, 'seed': seed, 'beta': 0.0 if ic == 0 else 0.4,
                'formulas': formulas, 'segments': SMALL, 'plan': plan, 'blueprints': blueprints,
                'llm': {'model_key': 'ollama-9b', 'name': 'fake', 'host': 'http://fake'}}
    return task, chats


@pytest.mark.parametrize("config", ["llm_mcts", "mcts_only", "random"])
def test_cell_of_every_configuration_writes_consistent_rows(cell_env, config):
    task, chats = cell_env
    result = rq.run_cell(task(config, 0.1, 'A2'))
    rows, run = result['checkpoints'], result['run']
    assert [r['budget'] for r in rows] == [20, 30, 60] and {r['a'] for r in rows} == {'A2'}
    assert run['iterations'] == 60 and run['config'] == config and run['formula'] == 'A2'
    assert np.isfinite(run['ic_search']) and run['wall_s'] <= run['elapsed_s'] + 1e-6
    for row in rows:
        assert row['near'] in (True, False) and 0.0 <= row['best_corr_top5'] <= 1.0
        assert len(json.loads(row['top_exprs'])) <= 5
        assert row['touched'] == (not np.isnan(row['touch_iterations']))
        if row['touched']:
            assert row['touch_iterations'] <= row['iterations']
    assert [r['wall_s'] for r in rows] == sorted(r['wall_s'] for r in rows)
    if config == 'llm_mcts':
        assert len(chats) == 1 and run['llm_requests'] == 1 and run['llm_s'] >= 0.0
        assert json.loads(run['feedback'])['n_new'] == 3 and len(json.loads(run['new_blueprints'])) == 3
        assert [r['llm_s'] for r in rows][:2] == [0.0, 0.0] and rows[2]['llm_s'] >= 0.0
    else:
        assert chats == [] and run['llm_requests'] == 0 and json.loads(run['new_blueprints']) == []


def test_shared_ic0_cell_scores_all_four_formulas_on_one_run(cell_env):
    task, _ = cell_env
    result = rq.run_cell(task('random', 0.0, rq.SHARED))
    rows = result['checkpoints']
    assert len(rows) == 4 * 3 and {r['a'] for r in rows} == {'A1', 'A2', 'A3', 'A4'}
    assert {r['run_formula'] for r in rows} == {''} and np.isnan(result['run']['ic_search'])
    by_budget = {(r['a'], r['budget']): r for r in rows}
    assert by_budget[('A1', 60)]['iterations'] == by_budget[('A4', 60)]['iterations'] == 60
    assert by_budget[('A1', 60)]['top_exprs'] == by_budget[('A4', 60)]['top_exprs']      # one search, four judgements


def test_same_cell_twice_gives_the_same_rows_except_for_clocks(cell_env):
    task, _ = cell_env
    drop = ['wall_s', 'llm_s', 'touch_wall_s']
    first = pd.DataFrame(rq.run_cell(task('mcts_only', 0.05, 'A1', 3))['checkpoints']).drop(columns=drop)
    second = pd.DataFrame(rq.run_cell(task('mcts_only', 0.05, 'A1', 3))['checkpoints']).drop(columns=drop)
    pd.testing.assert_frame_equal(first, second)


# --- CLI --------------------------------------------------------------------

def test_search_step_builds_the_cell_grid_calibrates_each_beta_once_and_attaches_llm(tmp_path, monkeypatch):
    parser = argparse.ArgumentParser()
    rq.add_rq1_parser(parser.add_subparsers(dest='command'))
    frame = hourly_frame()
    formulas = {name: formula for name, (formula, _) in pf.select_rq1_formulas(frame.loc[:SMALL.search_end]).items()}
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'planted_formulas.json').write_text(json.dumps({n: formula_to_dict(f) for n, f in formulas.items()}),
                                               encoding='utf-8')
    blueprints = tmp_path / 'blueprints.json'
    blueprints.write_text(json.dumps([{'name': 'a', 'macro_blueprint': 'ts_mean(?)'}]), encoding='utf-8')

    calls, captured = [], {}
    monkeypatch.setattr(rq, 'load_base', lambda segments: frame)
    monkeypatch.setattr(rq, 'get_beta', lambda base, ic, d, formula, workers, segments: calls.append((formula.expr, ic)) or 0.3)
    monkeypatch.setattr(rq, 'execute', lambda tasks, d, workers: captured.update(tasks=tasks, workers=workers))
    monkeypatch.setattr('strategy_workflows.BlueprintGeneration.create_chat',
                        lambda model: type('C', (), {'model': 'custom', 'host': 'http://h'})())
    args = parser.parse_args(['rq1', 'search', '--out-dir', str(out), '--blueprints', str(blueprints),
                              '--seeds', '1', '2', '--include-ic02', '--workers', '3', '--total-budget', '400',
                              '--phase-a', '200', '--chunk', '20', '--model', 'ollama-9b'])
    rq.run_rq1(args)

    tasks = captured['tasks']
    assert captured['workers'] == 3
    assert len(tasks) == 2 * (3 * (1 + 4 * 2) + 4)                  # 3 configs x (IC 0 + 4 A x 2 IC) + 4 A at IC 0.2
    assert len(calls) == len(set(calls)) == 4 * 3                   # each (A, IC) calibrated once
    llm_tasks = [t for t in tasks if t['config'] == 'llm_mcts']
    assert all(t['llm'] == {'model_key': 'ollama-9b', 'name': 'custom', 'host': 'http://h'} for t in tasks)
    assert all(t['plan'].total == 400 and t['plan'].phase_a == 200 and t['plan'].chunk == 20 for t in tasks)
    assert tasks[0]['plan'].checkpoints == (10_000, 25_000, 50_000, 75_000, 100_000)[:0]       # none fit in 400
    assert {t['beta'] for t in tasks if t['ic'] > 0} == {0.3} and {t['beta'] for t in tasks if t['ic'] == 0} == {0.0}
    assert len(llm_tasks) == 2 * (1 + 4 * 2 + 4)


def test_formulas_step_refuses_to_overwrite_without_force(tmp_path, monkeypatch):
    frame = hourly_frame()
    monkeypatch.setattr(rq, 'load_data', lambda tf, start, end: frame)
    parser = argparse.ArgumentParser()
    rq.add_rq1_parser(parser.add_subparsers(dest='command'))
    args = parser.parse_args(['rq1', 'formulas', '--out-dir', str(tmp_path)])
    rq.run_rq1(args)
    stored = json.loads((tmp_path / 'planted_formulas.json').read_text(encoding='utf-8'))
    assert list(stored) == ['A1', 'A2', 'A3', 'A4'] and stored['A1']['sign'] == -1.0
    with pytest.raises(SystemExit, match='exists'):
        rq.run_rq1(args)
    args.force = True
    rq.run_rq1(args)


def test_coverage_step_writes_the_region_report(tmp_path, capsys):
    out = tmp_path
    (out / 'planted_formulas.json').write_text(json.dumps(pf.formulas_to_dict(
        {n: (f, {'kind': 'classical'}) for n, f in pf.classical_formulas().items()})), encoding='utf-8')
    blueprints = out / 'blueprints.json'
    blueprints.write_text(json.dumps([{'name': 'wide', 'macro_blueprint': 'ts_mean(?)'},
                                      {'name': 'x', 'macro_blueprint': 'sub(ts_mean(?), ts_max(?))'}]), encoding='utf-8')
    parser = argparse.ArgumentParser()
    rq.add_rq1_parser(parser.add_subparsers(dest='command'))
    rq.run_rq1(parser.parse_args(['rq1', 'coverage', '--out-dir', str(out), '--blueprints', str(blueprints)]))
    report = json.loads((out / 'coverage.json').read_text(encoding='utf-8'))['formulas']
    assert report['A2']['expressing'] == ['wide'] and report['A2']['in_region']
    assert report['A1']['in_region'] is False and report['A1']['smallest'] is None
