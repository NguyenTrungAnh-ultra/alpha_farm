import json
import os

import numpy as np
import pandas as pd
import pytest

pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient

from strategy_workflows import RunPlantedSignal as planted_run
from strategy_workflows.PlantedSignal import Segments, formula_to_dict, mean_reversion_formula
from strategy_workflows.RunPlantedSignal import ORACLE_FIELDS, RUN_FIELDS, summarize_runs
from web import app as web_app
from web import planted as web_planted
from web import system as web_system

TINY = Segments(search_start='2020-01-01', train_end='2020-01-07', search_end='2020-01-12', eval_end='2020-01-17')


def run_row(mode, strength, seed, exact, near, oos):
    row = {c: 0.0 for c in RUN_FIELDS}
    row.update({'reward_mode': mode, 'strength': strength, 'seed': seed, 'iterations': 100,
                'ic_search': strength * 0.9, 'ic_eval': strength * 0.5, 'exact': exact, 'near': near,
                'oos_sharpe': oos, 'elapsed_s': 12.5, 'closest_expr': 'ts_mean(close, 10)',
                'top_exprs': json.dumps(['ts_mean(close, 10)', 'ts_max(high, 5)'])})
    return row


COMPLETE_ROWS = [
    run_row('soft', 0.0, 1, False, False, -1.0), run_row('soft', 0.0, 2, False, True, 0.5),
    run_row('soft', 0.0, 3, False, False, 0.2),
    run_row('soft', 0.05, 1, True, True, 1.5), run_row('soft', 0.05, 2, False, True, 0.7),
    run_row('soft', 0.05, 3, False, True, 2.0),
]


def write_dir(root, name, rows, log=None, segments=None, oracle=True, truncate_last=False):
    folder = root / name
    folder.mkdir()
    if rows:
        frame = pd.DataFrame(rows, columns=RUN_FIELDS)
        frame.to_csv(folder / 'runs.csv', index=False)
        if truncate_last:
            lines = (folder / 'runs.csv').read_text().splitlines()
            lines[-1] = lines[-1][:40]
            (folder / 'runs.csv').write_text(os.linesep.join(lines))
    if log is not None:
        (folder / 'search.log').write_text(log)
    if segments is not None:
        (folder / 'segments.json').write_text(json.dumps(segments.to_dict()))
    if oracle:
        pd.DataFrame([{**{c: 0.1 for c in ORACLE_FIELDS}, 'strength': s, 'seed': 1} for s in (0.0, 0.05)],
                     columns=ORACLE_FIELDS).to_csv(folder / 'oracle.csv', index=False)
    return folder


@pytest.fixture
def results(tmp_path):
    write_dir(tmp_path, 'planted_full', COMPLETE_ROWS, log='[planted] 6 runs, 20 blueprints\n', segments=TINY)
    write_dir(tmp_path, 'planted_partial', COMPLETE_ROWS[:4], log='[planted] 6 runs, 20 blueprints\n', truncate_last=True)
    (tmp_path / 'not_planted').mkdir()
    return tmp_path


@pytest.fixture
def client(results):
    return TestClient(web_app.create_app(str(results)))


def test_planted_page_renders_complete_and_partial(client):
    page = client.get('/')
    assert page.status_code == 200
    assert 'planted_full' in page.text and 'planted_partial' in page.text and 'not_planted' not in page.text
    progress = {f['name']: f for f in client.get('/api/planted/progress').json()}
    assert progress['planted_full']['done'] == 6 and progress['planted_full']['expected'] == 6
    assert progress['planted_full']['running'] is False
    assert progress['planted_full']['segments'] == TINY.to_dict()
    # half-written last row is not counted; log present and runs missing -> running
    assert progress['planted_partial']['done'] == 3
    assert progress['planted_partial']['running'] is True
    assert progress['planted_partial']['segments'] == Segments().to_dict()
    assert client.get('/planted/planted_partial').status_code == 200


def test_strength_table_equals_summarize_runs(client, results):
    expected = summarize_runs(pd.read_csv(results / 'planted_full' / 'runs.csv'))
    table = web_planted.strength_table(web_planted.read_runs(str(results / 'planted_full')))
    pd.testing.assert_frame_equal(table.reset_index(drop=True), expected.reset_index(drop=True), check_dtype=False)
    # counts shown on the page and numbers sent to the charts
    text = client.get('/planted/planted_full').text
    for row in expected.itertuples():
        assert f"{int(row.exact_count)}/{int(row.n_runs)}" in text
        assert f"{int(row.near_count)}/{int(row.n_runs)}" in text
    charts = client.get('/api/planted/charts').json()
    series = next(s for s in charts['near'] if s['label'] == 'planted_full')
    assert series['points'] == [[pytest.approx(r.ic_search), pytest.approx(r.near_rate)] for r in expected.itertuples()]
    oos = next(s for s in charts['oos'] if s['label'] == 'planted_full')
    assert [p[1] for p in oos['points']] == [pytest.approx(v) for v in expected['oos_sharpe_mean']]
    assert len(charts['oracle']) == 2


@pytest.mark.parametrize('url', [
    '/planted/nope', '/planted/not_planted', '/planted/..%2f..%2fetc/data', '/planted/../data',
    '/planted/planted_full%2f..%2f..%2fx', '/planted/planted_full/data?strength=0.03&seed=1',
    '/planted/planted_full/data?strength=0.05&seed=99',
])
def test_unknown_or_traversal_gives_404(client, url):
    assert client.get(url).status_code == 404


def test_system_api_survives_failing_nvidia_smi(client, monkeypatch):
    def broken(*args, **kwargs):
        raise FileNotFoundError('nvidia-smi')
    monkeypatch.setattr(web_system.subprocess, 'run', broken)
    data = client.get('/api/system').json()
    assert {'cpu_percent', 'cpu_per_core', 'ram', 'gpu', 'gpu_error', 'disk'} <= set(data)
    assert data['gpu'] is None and 'FileNotFoundError' in data['gpu_error']
    assert 0.0 <= data['ram']['percent'] <= 100.0 and data['disk']['free_gb'] > 0
    assert client.get('/system').status_code == 200


def test_data_page_uses_directory_segments(client, results, monkeypatch):
    rng = np.random.default_rng(0)
    index = pd.date_range('2020-01-01 09:00', periods=400, freq='1h')
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.003, len(index)))
    base = pd.DataFrame({'Open': close, 'High': close * 1.002, 'Low': close * 0.998, 'Close': close,
                         'Volume': rng.uniform(1000, 5000, len(index))}, index=index)
    formula = mean_reversion_formula()
    folder = results / 'planted_full'
    (folder / 'planted_formula.json').write_text(json.dumps(formula_to_dict(formula)))
    seen_segments = []
    monkeypatch.setattr(planted_run, 'load_base', lambda segments: seen_segments.append(segments) or base)
    key = planted_run.calibration_key(base, 0.05, formula, TINY)
    (folder / 'calibration.json').write_text(json.dumps({key: {'beta': 0.02}}))
    calls = []
    real_build = planted_run.build_planted_data

    def spy(base_frame, search_end, strength, seed, beta, formula_arg):
        calls.append((search_end, strength, seed, beta))
        return real_build(base_frame, search_end, strength, seed, beta, formula_arg)

    monkeypatch.setattr(planted_run, 'build_planted_data', spy)
    monkeypatch.setattr(web_app, '_planted_equity', lambda data, f, seed, mode: {
        'curve': pd.Series(np.linspace(1e9, 1.1e9, 20), index=data.evaluation.index[:20]),
        'z': 1.0, 'direction': 1.0, 'sharpe': 0.5, 'trades': 7})

    page = client.get('/planted/planted_full/data?strength=0.05&seed=2')
    assert page.status_code == 200
    assert seen_segments == [TINY]
    assert calls == [(TINY.search_end, 0.05, 2, 0.02), (TINY.search_end, 0.0, 2, 0.0)]
    assert 'c-equity' in page.text and 'c-prices' in page.text and '"labels"' in page.text

    # strength present in runs.csv but not calibrated: message instead of a calibration write
    (folder / 'calibration.json').write_text('{}')
    before = (folder / 'calibration.json').read_text()
    page = client.get('/planted/planted_full/data?strength=0.05&seed=2')
    assert 'calibration.json' in page.text and 'c-prices' not in page.text
    assert (folder / 'calibration.json').read_text() == before
