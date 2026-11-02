import json

import numpy as np
import pandas as pd
import pytest

from strategy_workflows import WalkForward as wf
from strategy_workflows.PlantedSignal import Segments, split_bars


def hourly_frame(start='2024-01-01', end='2024-05-31', seed=0):
    days = pd.bdate_range(start, end)
    index = pd.DatetimeIndex([d + pd.Timedelta(hours=9 + h) for d in days for h in range(8)], name='Datetime')
    rng = np.random.default_rng(seed)
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.002, len(index)))
    return pd.DataFrame({
        'Open': close * rng.uniform(0.999, 1.001, len(index)), 'High': close * rng.uniform(1.0, 1.003, len(index)),
        'Low': close * rng.uniform(0.997, 1.0, len(index)), 'Close': close,
        'Volume': rng.uniform(1000, 5000, len(index)),
    }, index=index)


SMALL = Segments(search_start='2024-01-01', train_end='2024-02-29', search_end='2024-04-30', eval_end='2024-05-31')


def test_window_table_boundaries():
    expected = [
        ('2021-06-30', '2022-06-30', '2022-12-31'), ('2021-12-31', '2022-12-31', '2023-06-30'),
        ('2022-06-30', '2023-06-30', '2023-12-31'), ('2022-12-31', '2023-12-31', '2024-06-30'),
        ('2023-06-30', '2024-06-30', '2024-12-31'), ('2023-12-31', '2024-12-31', '2025-06-30'),
        ('2024-06-30', '2025-06-30', '2025-12-31'),
    ]
    assert len(wf.WINDOWS) == 7
    for window, (train_end, search_end, eval_end) in zip(wf.WINDOWS, expected):
        assert window.search_start == '2018-08-13'
        assert (window.train_end, window.search_end, window.eval_end) == (train_end, search_end, eval_end)
    first = wf.WINDOWS[0]
    assert (first.validation_start, first.eval_start) == ('2021-07-01', '2022-07-01')
    assert wf.WINDOWS[1].validation_start == '2022-01-01'


def test_placebo_permutation_keeps_each_segments_returns_and_differs_across_sets_and_windows():
    frame = hourly_frame()
    bars = split_bars(frame)
    n_train, n_search = len(frame.loc[:SMALL.train_end]), len(frame.loc[:SMALL.search_end])
    perm = wf.permute_segments(bars, n_train, n_search, wf.placebo_seed(1, 1))
    for lo, hi in ((0, n_train), (n_train, n_search), (n_search, len(frame))):
        assert np.allclose(np.sort(perm['ret'].to_numpy()[lo:hi]), np.sort(bars['ret'].to_numpy()[lo:hi]))
    assert perm['ret'].iloc[0] == 0.0
    assert not np.allclose(perm['ret'].to_numpy(), bars['ret'].to_numpy())
    other_set = wf.permute_segments(bars, n_train, n_search, wf.placebo_seed(2, 1))
    other_window = wf.permute_segments(bars, n_train, n_search, wf.placebo_seed(1, 2))
    assert not np.allclose(perm['ret'].to_numpy(), other_set['ret'].to_numpy())
    assert not np.allclose(perm['ret'].to_numpy(), other_window['ret'].to_numpy())
    rebuilt = wf.placebo_frame(frame, SMALL, wf.placebo_seed(1, 1))
    assert rebuilt.index.equals(frame.index) and (rebuilt['Volume'].sum() == pytest.approx(frame['Volume'].sum()))


def test_placebo_seeds_are_unique_and_avoid_run_and_calibration_seeds():
    seeds = [wf.placebo_seed(k, w) for k in range(1, 200) for w in range(1, 100)]
    assert len(set(seeds)) == len(seeds)
    reserved = set(range(1, 6)) | set(range(1001, 1021))
    assert not reserved & set(seeds)
    assert min(seeds) > 1020
    with pytest.raises(ValueError):
        wf.placebo_seed(0, 1)


def fake_runner(task):
    row = {k: 0 for k in wf.RUN_FIELDS}
    row.update(mode=task['mode'], placebo_set=task['placebo_set'], window=task['window'], seed=task['seed'],
               eval_sharpe=1.0, elapsed_s=0.0)
    days = pd.date_range('2024-05-01', periods=3)
    return {'row': row, 'returns': pd.Series([0.001, -0.002, 0.003], index=days)}


def test_execute_skips_rows_already_in_runs_csv(tmp_path):
    out = str(tmp_path)
    frame = hourly_frame()
    tasks = wf.build_tasks('placebo', [SMALL, SMALL], [1], [], 1, frame, placebo_sets=2)
    assert len(tasks) == 4
    assert wf.execute(tasks[:2], out, workers=1, runner=fake_runner) == 2
    assert wf.execute(tasks, out, workers=1, runner=fake_runner) == 2
    assert wf.execute(tasks, out, workers=1, runner=fake_runner) == 0
    runs = pd.read_csv(tmp_path / 'runs.csv')
    assert len(runs) == 4 and not runs.duplicated(wf.RUN_KEY).any()
    returns = pd.read_csv(tmp_path / 'returns.csv')
    assert len(returns) == 12 and list(returns.columns) == wf.RETURN_FIELDS


@pytest.fixture
def config(tmp_path):
    path = tmp_path / 'blueprints.json'
    path.write_text(json.dumps([{'name': 'a', 'macro_blueprint': 'ts_mean(?)'},
                                {'name': 'b', 'macro_blueprint': 'ts_max(?)'}]), encoding='utf-8')
    folder = tmp_path / 'formula_set'
    folder.mkdir()
    (folder / 'formulas.json').write_text(json.dumps([{'name': 'f1', 'formula': 'ts_mean(pv_close, 5)'},
                                                      {'name': 'f2', 'formula': 'ts_max(pv_high, 3)'}]), encoding='utf-8')
    (folder / 'generation.json').write_text(json.dumps({'n': 2}), encoding='utf-8')

    def make(**kw):
        return wf.current_config(str(path), **{'n_blueprints': 2, 'iterations': 5000, 'seeds': [1, 2, 3, 4, 5],
                                               'data_sha256': 'x', 'formulas_path': str(folder / 'formulas.json'), **kw})
    make.folder = folder
    return path, make


def test_frozen_check_accepts_identical_and_refuses_changes(config):
    path, make = config
    frozen = {**make(), 'git_commit': 'abc'}
    frozen = json.loads(json.dumps(frozen))
    assert wf.verify_frozen(frozen, make(), lambda commit: []) == []
    assert any('iterations' in p for p in wf.verify_frozen(frozen, make(iterations=10), lambda c: []))
    assert any('seeds' in p for p in wf.verify_frozen(frozen, make(seeds=[1]), lambda c: []))
    assert any('data_sha256' in p for p in wf.verify_frozen(frozen, make(data_sha256='y'), lambda c: []))
    assert any('code changed' in p for p in wf.verify_frozen(frozen, make(), lambda c: ['core_engine/x.py']))
    path.write_text(json.dumps([{'name': 'a', 'macro_blueprint': 'ts_mean(?)'},
                                {'name': 'b', 'macro_blueprint': 'ts_min(?)'}]), encoding='utf-8')
    assert any('blueprints_sha256' in p for p in wf.verify_frozen(frozen, make(), lambda c: []))


def test_frozen_config_pins_the_required_fields(config):
    _, make = config
    for key in ('reward_mode', 'reward_weights', 'windows', 'blueprints_path', 'blueprints_sha256', 'n_blueprints',
                'iterations', 'seeds', 'timeframe', 'max_ranked', 'top_k', 'mcts_max_depth', 'data_sha256'):
        assert key in make()
    assert make()['reward_mode'] == 'sharpe' and len(make()['windows']) == 7


def frozen_of(make):
    return json.loads(json.dumps({**make(), 'git_commit': 'abc'}))


def problems_of(frozen, current):
    return wf.verify_frozen(frozen, current, lambda c: [])


def test_freeze_pins_the_inputs_of_every_configuration(config):
    _, make = config
    frozen = frozen_of(make)
    for key in ('blueprints_path', 'blueprints_sha256', 'formulas_path', 'formulas_sha256', 'n_formulas',
                'formulas_generation_sha256', 'llm_only_grid', 'tsmom_grid', 'reference_position_scale',
                'seeds_by_system', 'budget_plan', 'llm_model'):
        assert key in frozen, key
    assert frozen['n_formulas'] == 2 and len(frozen['formulas_sha256']) == 64
    assert frozen['llm_only_grid'] == {'rolling_windows': [2, 3, 5, 10], 'template_windows': [2, 3, 5, 7, 10],
                                       'sizes': {'NORMALIZED': 25, 'RATIO': 25, 'BOOLEAN': 1}}
    assert frozen['tsmom_grid']['lookback_sessions'] == {'day': 1, 'week': 5, 'month': 21}
    assert frozen['tsmom_grid']['selection'] == 'validation_sharpe'
    assert frozen['seeds_by_system'] == {'llm_mcts': [1, 2, 3, 4, 5], 'mcts_only': [1, 2, 3, 4, 5],
                                         'random': [1, 2, 3, 4, 5], 'llm_only': [1], 'buy_hold': [1], 'tsmom': [1]}
    assert frozen['formulas_sha256'] == wf.file_sha256(str(make.folder / 'formulas.json'))
    assert problems_of(frozen, make()) == []


def test_verify_refuses_when_the_formula_set_or_its_generation_record_changes(config):
    _, make = config
    frozen = frozen_of(make)
    (make.folder / 'generation.json').write_text(json.dumps({'n': 3}), encoding='utf-8')
    assert any('formulas_generation_sha256' in p for p in problems_of(frozen, make()))
    (make.folder / 'generation.json').write_text(json.dumps({'n': 2}), encoding='utf-8')
    assert problems_of(frozen, make()) == []
    moved = make.folder.parent / 'other'
    moved.mkdir()
    (moved / 'formulas.json').write_text((make.folder / 'formulas.json').read_text(encoding='utf-8'), encoding='utf-8')
    assert any('formulas_path' in p for p in problems_of(frozen, make(formulas_path=str(moved / 'formulas.json'))))
    (make.folder / 'formulas.json').write_text(json.dumps([{'name': 'f1', 'formula': 'ts_mean(pv_close, 5)'}]),
                                               encoding='utf-8')
    problems = problems_of(frozen, make())
    assert any('formulas_sha256' in p for p in problems) and any('n_formulas' in p for p in problems)


def test_verify_refuses_when_the_tsmom_grid_the_position_size_or_the_seed_plan_changes(config, monkeypatch):
    _, make = config
    frozen = frozen_of(make)
    monkeypatch.setattr(wf, 'TSMOM_LOOKBACK_SESSIONS', {'day': 1, 'week': 5, 'month': 22})
    assert any('tsmom_grid' in p for p in problems_of(frozen, make()))
    monkeypatch.undo()
    monkeypatch.setattr(wf, 'POSITION_SCALE', 0.5)
    assert any('reference_position_scale' in p for p in problems_of(frozen, make()))
    monkeypatch.undo()
    assert any('seeds_by_system' in p for p in problems_of(frozen, make(seeds=[1, 2])))
    assert any('budget_plan' in p for p in problems_of(frozen, make(plan=wf.wf_plan(1000, 500, 100))))
    assert any('llm_model' in p for p in problems_of(frozen, make(llm_model='ollama-9b')))


def test_verify_refuses_when_the_code_differs_from_the_frozen_commit(config):
    _, make = config
    frozen = frozen_of(make)
    assert any('code changed' in p for p in wf.verify_frozen(frozen, make(), lambda c: ['strategy_workflows/LLMOnly.py']))


def test_every_module_of_the_configurations_lives_under_a_checked_code_path():
    import os
    for module in ('LLMOnly', 'Baselines', 'Statistics', 'SearchConfigs', 'RandomSearch', 'WalkForward'):
        path = os.path.join('strategy_workflows', f'{module}.py').replace(os.sep, '/')
        assert os.path.exists(os.path.join(wf.PROJECT_ROOT, path))
        assert any(path.startswith(p + '/') or path == p for p in wf.CODE_PATHS), module


def freeze_env(tmp_path, monkeypatch):
    parser = argparse.ArgumentParser()
    wf.add_walkforward_parser(parser.add_subparsers(dest='command'))
    frame = hourly_frame()
    monkeypatch.setattr(wf, 'load_full_frame', lambda *a: frame)
    monkeypatch.setattr(wf, 'WINDOWS', [SMALL])
    monkeypatch.setattr(wf, 'current_commit', lambda: 'abc123')
    monkeypatch.setattr(wf.verify_frozen, '__defaults__', (lambda commit: [],))
    bp = tmp_path / 'bp.json'
    bp.write_text(json.dumps(TINY_BLUEPRINTS), encoding='utf-8')
    folder = tmp_path / 'fset'
    folder.mkdir()
    formulas = folder / 'formulas.json'
    formulas.write_text(json.dumps([{'name': 'f1', 'formula': 'ts_mean(pv_close, 5)'}]), encoding='utf-8')
    root = tmp_path / 'wf'
    base = ['--results-root', str(root), '--blueprints', str(bp), '--n-blueprints', '3']
    return parser, base, formulas, root


def test_freeze_step_needs_the_formula_set_and_real_step_refuses_after_it_changes(tmp_path, monkeypatch):
    parser, base, formulas, root = freeze_env(tmp_path, monkeypatch)
    with pytest.raises(SystemExit, match='--formulas'):
        wf.step_freeze(parser.parse_args(['walkforward', 'freeze'] + base))
    wf.step_freeze(parser.parse_args(['walkforward', 'freeze'] + base + ['--formulas', str(formulas)]))
    frozen = json.loads((root / 'frozen.json').read_text(encoding='utf-8'))
    assert frozen['git_commit'] == 'abc123' and frozen['formulas_sha256'] == wf.file_sha256(str(formulas))

    captured = {}
    monkeypatch.setattr(wf, 'execute', lambda tasks, out, workers: captured.update(tasks=tasks, out=out))
    wf.step_real(parser.parse_args(['walkforward', 'real', '--system', 'llm_only'] + base))   # formulas: frozen.json
    assert {t['seed'] for t in captured['tasks']} == {1} and captured['tasks'][0]['formulas'][0]['name'] == 'f1'
    assert captured['out'] == str(root / 'llm_only')

    formulas.write_text(json.dumps([{'name': 'f1', 'formula': 'ts_mean(pv_close, 3)'}]), encoding='utf-8')
    for system in ('llm_only', 'random', 'tsmom'):       # one frozen record guards every configuration
        with pytest.raises(SystemExit, match='formulas_sha256'):
            wf.step_real(parser.parse_args(['walkforward', 'real', '--system', system] + base))


def test_real_step_refuses_a_changed_tsmom_grid(tmp_path, monkeypatch):
    parser, base, formulas, root = freeze_env(tmp_path, monkeypatch)
    wf.step_freeze(parser.parse_args(['walkforward', 'freeze'] + base + ['--formulas', str(formulas)]))
    monkeypatch.setattr(wf, 'TSMOM_LOOKBACK_SESSIONS', {'day': 1, 'week': 5, 'month': 22})
    with pytest.raises(SystemExit, match='tsmom_grid'):
        wf.step_real(parser.parse_args(['walkforward', 'real', '--system', 'tsmom'] + base))


def test_summary_sharpe_matches_hand_computation_and_p_value_counts_ties():
    days = pd.date_range('2024-01-01', periods=4).strftime('%Y-%m-%d')

    def rows(mode, k, seed, values):
        return pd.DataFrame({'date': days, 'window': 1, 'seed': seed, 'mode': mode, 'placebo_set': k,
                             'return': values})

    real_a, real_b = [0.02, -0.01, 0.01, 0.01], [0.03, -0.01, 0.0, 0.02]
    tie = real_a
    frames = [rows('real', 0, 1, real_a), rows('real', 0, 2, real_b),
              rows('placebo', 1, 1, tie), rows('placebo', 2, 1, [0.0, 0.0, 0.0, 0.0]),
              rows('placebo', 3, 1, [0.001, 0.002, -0.001, 0.0])]
    summary = wf.summarize(pd.concat(frames))
    seed1 = np.array(real_a)
    expected = seed1.mean() / seed1.std(ddof=0) * np.sqrt(252)
    real = summary[summary['mode'] == wf.REAL_SEED1_MODE].iloc[0]
    assert real['sharpe'] == pytest.approx(expected)
    assert real['n_days'] == 4
    # set 1 equals the seed-1 series (ties, counts), set 2 is flat (NaN, excluded from K), set 3 is lower
    assert real['p_value'] == pytest.approx((1 + 1) / (2 + 1))
    assert np.isnan(summary[summary['placebo_set'] == 2]['sharpe'].iloc[0])


def test_p_value_floor_is_one_over_k_plus_one():
    days = ['2024-01-01', '2024-01-02', '2024-01-03']
    rows = [pd.DataFrame({'date': days, 'window': 1, 'seed': 1, 'mode': 'real', 'placebo_set': 0,
                          'return': [0.05, 0.04, 0.06]})]
    for k in (1, 2, 3):
        rows.append(pd.DataFrame({'date': days, 'window': 1, 'seed': 1, 'mode': 'placebo', 'placebo_set': k,
                                  'return': [0.01 * k, -0.01, 0.0]}))
    summary = wf.summarize(pd.concat(rows))
    assert summary[summary['mode'] == wf.REAL_SEED1_MODE]['p_value'].iloc[0] == pytest.approx(1 / 4)


def seed_returns(seed, values, mode='real', k=0):
    days = pd.date_range('2024-01-01', periods=len(values)).strftime('%Y-%m-%d')
    return pd.DataFrame({'date': days, 'window': 1, 'seed': seed, 'mode': mode, 'placebo_set': k, 'return': values})


def test_p_value_uses_seed_one_only_and_mean_row_is_descriptive():
    seed1 = [0.01, -0.01, 0.01, -0.01, 0.0, 0.01]
    seed2 = [0.03, 0.02, 0.03, 0.02, 0.04, 0.03]            # lifts the mean series far above seed 1
    placebo = [0.02, -0.01, 0.015, -0.005, 0.01, 0.0]       # Sharpe between the seed-1 and mean series
    frames = [seed_returns(1, seed1), seed_returns(2, seed2), seed_returns(1, placebo, 'placebo', 1)]
    summary = wf.summarize(pd.concat(frames))
    first = summary[summary['mode'] == wf.REAL_SEED1_MODE].iloc[0]
    mean = summary[summary['mode'] == wf.REAL_MEAN_MODE].iloc[0]
    placebo_sharpe = summary[summary['mode'] == 'placebo']['sharpe'].iloc[0]
    assert mean['sharpe'] > placebo_sharpe > first['sharpe']
    assert first['p_value'] == pytest.approx(1.0)           # the mean row would give 1/2
    assert np.isnan(mean['p_value']) and mean['n_days'] == 6


def test_missing_seed_one_leaves_p_nan_and_says_why(capsys):
    frames = [seed_returns(2, [0.01, -0.01, 0.02]), seed_returns(1, [0.0, 0.01, -0.01], 'placebo', 1)]
    summary = wf.summarize(pd.concat(frames))
    assert wf.REAL_SEED1_MODE not in set(summary['mode'])
    assert summary['p_value'].isna().all() and wf.REAL_MEAN_MODE in set(summary['mode'])
    assert 'seed 1' in capsys.readouterr().out


@pytest.mark.slow
def test_run_window_end_to_end_tiny(tmp_path):
    frame = hourly_frame()
    blueprints = [{'name': 'bp', 'macro_blueprint': 'mult(ts_mean(?), ts_zscore(ts_max(?)))'}]
    for mode, k in (('real', 0), ('placebo', 1)):
        task = {'mode': mode, 'placebo_set': k, 'window': 1, 'seed': 1, 'segments': SMALL, 'frame': frame,
                'data_seed': wf.placebo_seed(k, 1) if k else 0, 'iterations': 30, 'blueprints': blueprints}
        outcome = wf.run_window(task)
        row = outcome['row']
        assert row['mode'] == mode and row['evaluations'] > 0 and 'failed' in row
        assert outcome['returns'].index.min() >= pd.Timestamp(SMALL.eval_start)
        assert outcome['returns'].index.max() <= pd.Timestamp(SMALL.eval_end)
        wf.append_run(str(tmp_path), 1, outcome)
    assert len(pd.read_csv(tmp_path / 'runs.csv')) == 2


# --- search systems -----------------------------------------------------------

import argparse

from tests.test_batched_blueprints import batch_reply, skeletons

TINY_PLAN = wf.wf_plan(total=60, phase_a=30, chunk=10)
TINY_BLUEPRINTS = [{'name': f'B{i}', 'macro_blueprint': b} for i, b in enumerate(skeletons(16)[:3])]


class TinyChat:
    model, host = 'fake', 'http://fake'

    def __init__(self):
        self.prompts, self.options = [], []

    def send(self, prompt, schema=None, options=None):
        self.prompts.append(prompt)
        self.options.append(options)
        return batch_reply(skeletons(16)[8:11], 'New')


def window_task(system, mode='real', k=0, seed=1):
    return {'mode': mode, 'placebo_set': k, 'window': 1, 'seed': seed, 'segments': SMALL, 'frame': hourly_frame(),
            'data_seed': wf.placebo_seed(k, 1) if k else 0, 'iterations': 20, 'blueprints': TINY_BLUEPRINTS,
            'system': system, 'plan': TINY_PLAN, 'llm': {'model_key': 'ollama-9b', 'name': 'fake', 'host': 'http://fake'}}


@pytest.fixture
def chats(monkeypatch):
    made = []
    monkeypatch.setattr(wf, 'create_worker_chat', lambda spec: made.append(TinyChat()) or made[-1])
    return made


@pytest.mark.parametrize("system", ["llm_mcts", "mcts_only", "random"])
@pytest.mark.parametrize("mode, k", [("real", 0), ("placebo", 1)])
def test_run_window_with_each_search_system(system, mode, k, chats):
    outcome = wf.run_window(window_task(system, mode, k))
    row = outcome['row']
    assert row['system'] == system and row['mode'] == mode and row['iterations'] == TINY_PLAN.total
    assert row['evaluations'] > 0 and row['n_ranked'] > 0 and set(wf.RUN_FIELDS) == set(row)
    assert outcome['returns'].index.min() >= pd.Timestamp(SMALL.eval_start)
    if system == 'llm_mcts':
        assert len(chats) == 1 and row['llm_requests'] == 1
        assert len(json.loads(row['new_blueprints'])) == 3 and json.loads(row['feedback'])['n_new'] == 3
        assert [o['seed'] for o in chats[0].options] == [json.loads(row['feedback'])['seed']]
    else:
        assert chats == [] and row['llm_requests'] == 0 and json.loads(row['new_blueprints']) == []


def without_clock(feedback_json):
    """The feedback record minus `llm_s`, a measured wall time that never repeats between two runs."""
    record = json.loads(feedback_json)
    record.pop('llm_s')
    return record


def test_run_window_is_reproducible_and_seed_of_the_llm_follows_the_run(chats):
    first = wf.run_window(window_task('llm_mcts'))['row']
    second = wf.run_window(window_task('llm_mcts'))['row']
    for column in ('top', 'evaluations', 'new_blueprints'):
        assert first[column] == second[column]
    assert without_clock(first['feedback']) == without_clock(second['feedback'])
    other_seed = wf.run_window(window_task('llm_mcts', seed=2))['row']
    assert json.loads(other_seed['feedback'])['seed'] != json.loads(first['feedback'])['seed']
    assert chats[0].prompts == chats[1].prompts                 # same run, same question


def test_feedback_record_differs_between_identical_runs_only_in_the_measured_llm_time(chats, monkeypatch):
    """
    Reproduces the intermittent failure of the reproducibility test: `llm_s` is a wall time. The Windows clock ticks
    every ~16 ms, so two runs of a fast fake LLM usually read 0.0 twice, but a run that straddles a tick differs.
    """
    import itertools
    import types
    ticks = itertools.count()
    monkeypatch.setattr('strategy_workflows.BlueprintGeneration.time',
                        types.SimpleNamespace(time=lambda: next(ticks) ** 2 * 0.01))     # never the same step twice
    first = wf.run_window(window_task('llm_mcts'))['row']
    second = wf.run_window(window_task('llm_mcts'))['row']
    assert first['feedback'] != second['feedback']
    assert json.loads(first['feedback'])['llm_s'] != json.loads(second['feedback'])['llm_s']
    assert without_clock(first['feedback']) == without_clock(second['feedback'])
    assert first['top'] == second['top'] and first['new_blueprints'] == second['new_blueprints']


def test_run_window_defaults_to_the_old_sequential_search_without_a_system():
    task = window_task('oneshot')
    del task['system']
    row = wf.run_window(task)['row']
    assert row['system'] == 'oneshot' and row['iterations'] == 20 and row['llm_requests'] == 0


def test_build_tasks_carry_system_plan_and_llm():
    frame = hourly_frame()
    plan = wf.wf_plan(40, 20, 10)
    tasks = wf.build_tasks('real', [SMALL], [1, 2], [], 5, frame, system='random', plan=plan, llm={'name': 'x'})
    assert {t['system'] for t in tasks} == {'random'} and tasks[0]['plan'] is plan and tasks[0]['llm'] == {'name': 'x'}
    assert wf.build_tasks('real', [SMALL], [1], [], 5, frame)[0]['system'] == 'llm_mcts'
    with pytest.raises(ValueError, match='system'):
        wf.build_tasks('real', [SMALL], [1], [], 5, frame, system='nonsense')
    assert wf.wf_plan().checkpoints == () and wf.wf_plan(10, 5, 5).total == 10


def test_frozen_config_pins_the_budget_plan_and_the_llm_model(config):
    _, make = config
    frozen = json.loads(json.dumps({**make(), 'git_commit': 'abc'}))
    assert frozen['budget_plan']['total'] == 100000 and frozen['budget_plan']['phase_a'] == 50000
    assert frozen['budget_plan']['checkpoints'] == [] and frozen['llm_model'] == 'ollama-local'
    changed = make(plan=wf.wf_plan(50000, 25000, 500))
    assert any('budget_plan' in p for p in wf.verify_frozen(frozen, changed, lambda c: []))
    assert any('llm_model' in p for p in wf.verify_frozen(frozen, make(llm_model='ollama-9b'), lambda c: []))


def test_cli_defaults_to_the_feedback_system_and_names_the_folder_after_it(tmp_path):
    parser = argparse.ArgumentParser()
    wf.add_walkforward_parser(parser.add_subparsers(dest='command'))
    args = parser.parse_args(['walkforward', 'summary', '--results-root', str(tmp_path)])
    assert args.system == 'llm_mcts' and wf.out_dir_of(args) == str(tmp_path / 'llm_mcts')
    args = parser.parse_args(['walkforward', 'summary', '--results-root', str(tmp_path), '--system', 'random'])
    assert wf.out_dir_of(args) == str(tmp_path / 'random')
    args = parser.parse_args(['walkforward', 'summary', '--results-root', str(tmp_path), '--system', 'oneshot',
                              '--config', 'old_style'])
    assert wf.out_dir_of(args) == str(tmp_path / 'old_style')
    for system in ('llm_only', 'buy_hold', 'tsmom'):
        assert parser.parse_args(['walkforward', 'summary', '--results-root', str(tmp_path),
                                  '--system', system]).system == system
    with pytest.raises(SystemExit):
        parser.parse_args(['walkforward', 'real', '--system', 'nonsense'])


def test_placebo_step_passes_system_plan_and_llm_to_the_tasks(tmp_path, monkeypatch):
    parser = argparse.ArgumentParser()
    wf.add_walkforward_parser(parser.add_subparsers(dest='command'))
    frame = hourly_frame()
    captured = {}
    monkeypatch.setattr(wf, 'load_full_frame', lambda *a: frame)
    monkeypatch.setattr(wf, 'WINDOWS', [SMALL, SMALL])
    monkeypatch.setattr(wf, 'execute', lambda tasks, out, workers: captured.update(tasks=tasks, out=out))
    monkeypatch.setattr('strategy_workflows.BlueprintGeneration.create_chat',
                        lambda model: type('C', (), {'model': 'custom', 'host': 'http://h'})())
    bp = tmp_path / 'bp.json'
    bp.write_text(json.dumps(TINY_BLUEPRINTS), encoding='utf-8')
    args = parser.parse_args(['walkforward', 'placebo', '--results-root', str(tmp_path), '--blueprints', str(bp),
                              '--sets', '1', '--total-budget', '200', '--phase-a', '100', '--chunk', '20'])
    wf.step_placebo(args)
    task = captured['tasks'][0]
    assert task['system'] == 'llm_mcts' and task['plan'].total == 200 and task['plan'].phase_a == 100
    assert task['plan'].chunk == 20 and task['plan'].checkpoints == ()
    assert task['llm'] == {'model_key': 'ollama-local', 'name': 'custom', 'host': 'http://h'}
    assert captured['out'] == str(tmp_path / 'llm_mcts')
    args = parser.parse_args(['walkforward', 'placebo', '--results-root', str(tmp_path), '--blueprints', str(bp),
                              '--sets', '1', '--system', 'random'])
    wf.step_placebo(args)
    assert captured['tasks'][0]['llm'] is None and captured['out'] == str(tmp_path / 'random')
