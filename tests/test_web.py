import json
import math

import numpy as np
import pandas as pd
import pytest

pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient

from strategy_workflows import RunPlantedSignal as planted_run
from strategy_workflows.PlantedSignal import Segments, formula_to_dict, mean_reversion_formula
from strategy_workflows.RunPlantedSignal import RUN_FIELDS, summarize_runs
from web import app as web_app
from web import method as web_method
from web import planted as web_planted
from web import system as web_system
from web import thesis

TINY = Segments(search_start='2020-01-01', train_end='2020-01-07', search_end='2020-01-12', eval_end='2020-01-17')
FOLDER = web_planted.THESIS_PLANTED_DIR


def run_row(mode, strength, seed, exact, near, oos, corr=0.3, best=0.2):
    row = {c: 0.0 for c in RUN_FIELDS}
    row.update({'reward_mode': mode, 'strength': strength, 'seed': seed, 'iterations': 100,
                'ic_search': strength * 0.9, 'ic_eval': strength * 0.5, 'exact': exact, 'near': near,
                'oos_sharpe': oos, 'elapsed_s': 12.5, 'closest_expr': 'ts_mean(close, 10)', 'closest_corr': corr, 'best_corr': best, 'closest_val_rank': 24,
                'top_exprs': json.dumps(['ts_mean(close, 10)', 'ts_max(high, 5)'])})
    return row


ROWS = [
    run_row('sharpe', 0.0, 1, False, False, -1.0), run_row('sharpe', 0.0, 2, False, True, 0.5),
    run_row('sharpe', 0.0, 3, False, False, 0.2),
    run_row('sharpe', 0.05, 1, True, True, 1.5, 0.9), run_row('sharpe', 0.05, 2, False, True, 0.7, 0.8),
    run_row('sharpe', 0.05, 3, False, True, 2.0, 0.75),
    run_row('sharpe', 0.05, 3, False, False, 1.0, 0.95, 0.412),  # rerun of the same key replaces the row above
]
POSITIONS = [{'strength': s, 'seed': k, 'best_pos_corr': v, 'best_agree_active': 0.5, 'closest_corr': 0.3,
              'a_flat_share': 0.1}
             for s, k, v in ((0.0, 1, 0.05), (0.0, 2, 0.15), (0.05, 1, 0.5), (0.05, 2, 0.7))]


def write_folder(root, name, rows, positions=None, formula=True):
    folder = root / name
    folder.mkdir()
    pd.DataFrame(rows, columns=RUN_FIELDS).to_csv(folder / 'runs.csv', index=False)
    (folder / 'segments.json').write_text(json.dumps(TINY.to_dict()))
    if positions is not None:
        (folder / 'positions_vs_a.json').write_text(json.dumps(positions))
    if formula:
        (folder / 'planted_formula.json').write_text(json.dumps(formula_to_dict(mean_reversion_formula())))
    return folder


@pytest.fixture
def results(tmp_path):
    write_folder(tmp_path, FOLDER, ROWS, POSITIONS)
    # Other folders must never reach the pages.
    write_folder(tmp_path, 'planted_run3_old', [run_row('soft', 0.0, 1, True, True, 9.0)])
    return tmp_path


@pytest.fixture
def client(results):
    return TestClient(web_app.create_app(str(results)))


ALL_PAGES = ['/', '/data', '/method', '/results/planted', '/results/planted/illustration', '/results/placebo',
             '/results/rq1', '/results/walkforward', '/system']


@pytest.mark.parametrize('url', ALL_PAGES)
def test_every_page_renders(client, url):
    assert client.get(url).status_code == 200


@pytest.mark.parametrize('url', ALL_PAGES)
def test_pages_render_without_result_folder(tmp_path, url):
    page = TestClient(web_app.create_app(str(tmp_path))).get(url)
    assert page.status_code == 200


def test_planted_page_without_folder_says_missing(tmp_path):
    text = TestClient(web_app.create_app(str(tmp_path))).get('/results/planted').text
    assert 'chưa có' in text and 'Bảng 4.1' in text


def test_pipeline_redirects_to_method(client):
    response = client.get('/pipeline', follow_redirects=False)
    assert response.status_code in (302, 307) and response.headers['location'] == '/method'


def test_planted_page_shows_no_other_folder_or_reward_mode(client):
    text = client.get('/results/planted').text
    assert 'planted_run3_old' not in text and 'planted_window1' not in text
    for word in ('soft', 'gated', 'reward_mode', 'oracle', 'đang chạy'):
        assert word not in text
    assert '9.00' not in text  # the other folder's Sharpe


def test_near_table_counts_match_summarize_runs(client, results):
    expected = summarize_runs(pd.read_csv(results / FOLDER / 'runs.csv'))
    text = client.get('/results/planted').text
    assert len(expected) == 2
    for row in expected.itertuples():
        assert f"{int(row.near_count)}/{int(row.n_runs)}" in text
        assert f"{int(row.exact_count)}/{int(row.n_runs)}" in text
    # the rerun (seed 3 at 0.05) replaced the old row: 2 of 3 near, not 3 of 4
    assert '2/3' in text and '3/4' not in text


def test_planted_page_content(client):
    text = client.get('/results/planted').text
    for label in ('Bảng 4.1', 'Hình 4.1', 'Hình 4.2', 'Bảng 4.2', 'Bảng 4.3', 'RQ2'):
        assert label in text
    assert web_planted.read_formula_expr(str(client.app.state.results_root) + '/' + FOLDER) in text.replace('&#39;', "'")
    assert '/results/planted/illustration' in text
    assert 'Bảng 4.2' in text and 'nhiễu' in text


def test_positions_block_missing_file(tmp_path):
    write_folder(tmp_path, FOLDER, ROWS, positions=None)
    text = TestClient(web_app.create_app(str(tmp_path))).get('/results/planted').text
    assert 'chưa có' in text and 'Bảng 4.2' in text


def test_wilson_interval_known_values():
    low, high = web_planted.wilson_interval(6, 10)
    assert low == pytest.approx(0.3127, abs=1e-3) and high == pytest.approx(0.8318, abs=1e-3)
    low, high = web_planted.wilson_interval(0, 5)
    assert low == 0.0 and high == pytest.approx(0.4345, abs=1e-3)
    assert all(math.isnan(v) for v in web_planted.wilson_interval(0, 0))


def test_strength_table_has_wilson_bounds(results):
    rows = web_planted.strength_table(web_planted.read_runs(str(results / FOLDER)))
    by_strength = {r['strength']: r for r in rows}
    assert by_strength[0.05]['near_count'] == 2 and by_strength[0.05]['n_runs'] == 3
    assert (by_strength[0.05]['near_low'], by_strength[0.05]['near_high']) == web_planted.wilson_interval(2, 3)


def test_readings_are_computed_from_data(results):
    rows = web_planted.strength_table(web_planted.read_runs(str(results / FOLDER)))
    assert 'IC 0: 1/3' in thesis.reading_table(rows) and 'IC 0.05: 2/3' in thesis.reading_table(rows)
    positions = web_planted.position_table(POSITIONS)
    assert '0.15' in thesis.reading_positions(positions)  # noise maximum at IC 0
    assert '0.60' in thesis.reading_positions(positions)  # mean at IC 0.05


def test_system_api_survives_failing_nvidia_smi(client, monkeypatch):
    def broken(*args, **kwargs):
        raise FileNotFoundError('nvidia-smi')
    monkeypatch.setattr(web_system.subprocess, 'run', broken)
    data = client.get('/api/system').json()
    assert {'cpu_percent', 'cpu_per_core', 'ram', 'gpu', 'gpu_error', 'disk'} <= set(data)
    assert data['gpu'] is None and 'FileNotFoundError' in data['gpu_error']
    assert 0.0 <= data['ram']['percent'] <= 100.0 and data['disk']['free_gb'] > 0
    assert client.get('/system').status_code == 200


def test_removed_routes_are_gone(client):
    for url in ('/planted', '/planted/planted_window1', '/api/planted/progress', '/api/planted/charts'):
        assert client.get(url).status_code == 404


def test_illustration_uses_thesis_folder_segments(client, results, monkeypatch):
    rng = np.random.default_rng(0)
    index = pd.date_range('2020-01-01 09:00', periods=400, freq='1h')
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.003, len(index)))
    base = pd.DataFrame({'Open': close, 'High': close * 1.002, 'Low': close * 0.998, 'Close': close,
                         'Volume': rng.uniform(1000, 5000, len(index))}, index=index)
    formula = mean_reversion_formula()
    folder = results / FOLDER
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

    page = client.get('/results/planted/illustration?strength=0.05&seed=2')
    assert page.status_code == 200
    assert seen_segments == [TINY]
    assert calls == [(TINY.search_end, 0.05, 2, 0.02), (TINY.search_end, 0.0, 2, 0.0)]
    assert 'c-equity' in page.text and 'c-prices' in page.text and thesis.ILLUSTRATION_TITLE in page.text
    assert 'planted_run3_old' not in page.text and 'soft' not in page.text

    # a strength that was not calibrated gives a message and never writes calibration.json
    (folder / 'calibration.json').write_text('{}')
    page = client.get('/results/planted/illustration?strength=0.05&seed=2')
    assert 'hiệu chỉnh' in page.text and 'c-prices' not in page.text
    assert (folder / 'calibration.json').read_text() == '{}'


@pytest.mark.parametrize('query', ['?strength=0.03&seed=1', '?strength=0.05&seed=99'])
def test_illustration_unknown_selection_gives_404(client, query):
    assert client.get('/results/planted/illustration' + query).status_code == 404


def test_method_page_lists_every_node_and_windows(tmp_path):
    from strategy_workflows.WalkForward import WINDOWS
    from web import pipeline
    html = TestClient(web_app.create_app(tmp_path)).get('/method').text
    for node in pipeline.NODES:
        assert f'id="node-{node["id"]}"' in html
        assert node['label'].split()[0] in html
    for window in WINDOWS:
        assert window.eval_end in html and window.train_end in html
    assert 'chưa có' in html  # no blueprint set in the temp root
    for question in pipeline.THESIS['rqs']:
        assert f'data-nodes="{" ".join(question["nodes"])}"' in html


def test_blueprint_summary_reads_roots(tmp_path):
    path = tmp_path / web_method.BLUEPRINT_SET
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{'name': 'a', 'macro_blueprint': 'sub(ts_mean(?), 1)'},
                                {'name': 'b', 'macro_blueprint': 'sub(?, ?)'},
                                {'name': 'c', 'macro_blueprint': 'mult(?, ?)'}]))
    summary = web_method.blueprint_summary(str(tmp_path))
    assert summary == {'count': 3, 'roots': [('sub', 2), ('mult', 1)]}
    assert web_method.blueprint_summary(str(tmp_path / 'nowhere')) is None


def test_overview_has_thesis_header_and_progress(client):
    from web import pipeline
    html = client.get('/').text
    assert pipeline.THESIS['title'] in html and pipeline.THESIS['title_vi'] in html
    for question in pipeline.THESIS['rqs']:
        assert question['id'] in html
    for item in thesis.ITEMS:
        assert item['label'] in html


def test_progress_status_follows_availability():
    rows = {r['label']: r for r in thesis.progress_rows({'planted_runs': True})}
    assert rows['Bảng 4.1']['status'] == 'done' and rows['Bảng 4.2']['status'] == 'none'
    rows = {r['label']: r for r in thesis.progress_rows({})}
    assert rows['Bảng 4.1']['status'] == 'none' and rows['Hình 4.3']['status'] == 'none'


def test_nav_follows_chapter_order(client):
    html = client.get('/').text
    order = ['href="/"', 'href="/data"', 'href="/method"', 'href="/results/planted"', 'href="/results/placebo"',
             'href="/results/rq1"', 'href="/results/walkforward"', 'Công cụ (ngoài luận văn)', 'href="/system"']
    positions = [html.index(o) for o in order]
    assert positions == sorted(positions)


def test_web_does_not_reference_docs():
    from pathlib import Path
    for path in Path(web_app.__file__).parent.rglob('*'):
        if path.suffix in ('.py', '.html'):
            assert 'docs/' not in path.read_text(encoding='utf-8'), path.name


def test_pipeline_data_is_consistent():
    from web import pipeline
    ids = [n['id'] for n in pipeline.NODES]
    assert len(ids) == len(set(ids))
    group_ids = {g['id'] for g in pipeline.GROUPS}
    for node in pipeline.NODES:
        assert node['status'] in pipeline.STATUSES
        assert node['group'] in group_ids
    for edge in pipeline.EDGES:
        assert edge['from'] in ids and edge['to'] in ids
    for question in pipeline.THESIS['rqs']:
        assert set(question['nodes']) <= set(ids)
    note = next(n for n in pipeline.NODES if n['id'] == 'rq2_planted')
    assert 'ngữ pháp cũ' not in ' '.join(note['details'])


def test_seed_table_separates_top5_and_all_candidates(client):
    # seed 3 at 0.05: closest candidate correlates 0.95 but the top-5 only reaches 0.412 and is not near
    rows = {(r['strength'], r['seed']): r for r in web_planted.seed_table(
        web_planted.read_runs(str(client.app.state.results_root) + '/' + FOLDER))}
    row = rows[(0.05, 3)]
    assert row['near'] is False and row['closest_corr'] == pytest.approx(0.95) and row['best_corr'] == pytest.approx(0.412)
    text = client.get('/results/planted').text
    assert '0.412' in text and '0.950' in text and 'Tương quan cao nhất trong top-5' in text
    assert 'hạng kiểm định' in text.lower() or 'Hạng kiểm định' in text
