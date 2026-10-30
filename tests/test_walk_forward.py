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
    return path, lambda **kw: wf.current_config(str(path), **{'n_blueprints': 2, 'iterations': 5000,
                                                              'seeds': [1, 2, 3, 4, 5], 'data_sha256': 'x', **kw})


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


def test_summary_sharpe_matches_hand_computation_and_p_value_counts_ties():
    days = pd.date_range('2024-01-01', periods=4).strftime('%Y-%m-%d')

    def rows(mode, k, seed, values):
        return pd.DataFrame({'date': days, 'window': 1, 'seed': seed, 'mode': mode, 'placebo_set': k,
                             'return': values})

    real_a, real_b = [0.01, -0.01, 0.02, 0.0], [0.03, -0.01, 0.0, 0.02]
    tie = [0.02, -0.01, 0.01, 0.01]
    frames = [rows('real', 0, 1, real_a), rows('real', 0, 2, real_b),
              rows('placebo', 1, 1, tie), rows('placebo', 2, 1, [0.0, 0.0, 0.0, 0.0]),
              rows('placebo', 3, 1, [0.001, 0.002, -0.001, 0.0])]
    summary = wf.summarize(pd.concat(frames))
    mean_series = np.array([0.02, -0.01, 0.01, 0.01])
    expected = mean_series.mean() / mean_series.std(ddof=0) * np.sqrt(252)
    real = summary[summary['mode'] == 'real'].iloc[0]
    assert real['sharpe'] == pytest.approx(expected)
    assert real['n_days'] == 4
    # set 1 ties the real Sharpe (counts), set 2 is flat (NaN, excluded from K), set 3 is lower
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
    assert summary[summary['mode'] == 'real']['p_value'].iloc[0] == pytest.approx(1 / 4)


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
