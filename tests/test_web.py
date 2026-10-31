import json
import math

import numpy as np
import pandas as pd
import pytest
from scipy.stats import fisher_exact

pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient

from strategy_workflows import RunPlantedSignal as planted_run
from strategy_workflows import RunRQ1 as rq
from strategy_workflows import Statistics as st
from strategy_workflows.GrammarSize import count_completions, count_grammar
from strategy_workflows.PlantedSignal import Segments, formula_to_dict, mean_reversion_formula
from strategy_workflows.SearchConfigs import BudgetPlan
from strategy_workflows.SemanticCompiler import SemanticCompiler
from web import app as web_app
from web import method as web_method
from web import planted as web_planted
from web import rq1 as web_rq1
from web import system as web_system
from web import thesis

TINY = Segments(search_start='2020-01-01', train_end='2020-01-07', search_end='2020-01-12', eval_end='2020-01-17')
FOLDER = web_planted.THESIS_PLANTED_DIR
BUDGETS = (10_000, 50_000, 100_000)
BLUEPRINTS = [{'name': 'HighVolMeanReversion', 'macro_blueprint': 'not_(greater_than(ts_max(?), ts_mean(?)))'},
              {'name': 'Spread', 'macro_blueprint': 'sub(ts_mean(?), ts_min(?))'}]

# Near-recovery counts out of 10 seeds per (configuration, A, IC) at the last budget; other cells are 0.
NEAR_100K = {
    ('llm_mcts', 'A1'): {0.0: 0, 0.05: 2, 0.1: 6}, ('llm_mcts', 'A2'): {0.0: 0, 0.05: 0, 0.1: 1},
    ('llm_mcts', 'A3'): {0.0: 0, 0.05: 1, 0.1: 7}, ('llm_mcts', 'A4'): {0.0: 1, 0.05: 1, 0.1: 2},
    ('mcts_only', 'A1'): {0.0: 0, 0.05: 1, 0.1: 2}, ('mcts_only', 'A2'): {0.0: 0, 0.05: 0, 0.1: 1},
    ('mcts_only', 'A3'): {0.0: 0, 0.05: 1, 0.1: 3}, ('mcts_only', 'A4'): {0.0: 0, 0.05: 0, 0.1: 0},
}


def checkpoint_frame(near_last=NEAR_100K, seeds=10):
    """checkpoints.csv rows in the layout of RunRQ1; earlier budgets get half of the last budget's count."""
    rows = []
    for (config, name), levels in near_last.items():
        for ic, last in levels.items():
            for budget in BUDGETS:
                k = last if budget == BUDGETS[-1] else last // 2
                for seed in range(1, seeds + 1):
                    hit = seed <= k
                    rows.append({'config': config, 'ic': ic, 'run_formula': '' if ic == 0 else name, 'seed': seed,
                                 'a': name, 'budget': budget, 'near': hit, 'best_corr_top5': 0.5, 'closest_corr': 0.6,
                                 'touched': hit, 'touch_iterations': 500.0 * seed if hit else np.nan,
                                 'touch_evaluations': 500.0 * seed if hit else np.nan,
                                 'touch_wall_s': 10.0 * seed if hit else np.nan})
    return pd.DataFrame(rows)


def formulas_json():
    base = formula_to_dict(mean_reversion_formula())
    kinds = {'A1': 'classical', 'A2': 'classical', 'A3': 'random', 'A4': 'random'}
    return {name: dict(base, selection={'kind': kind, 'adf_p': 1e-6 * (i + 1), 'crowding_share': 0.002 * (i + 1)})
            for i, (name, kind) in enumerate(kinds.items())}


def coverage_json():
    empty = {'fits_depth_limit': True, 'in_region': False, 'expressing': [], 'verbatim': [], 'completions': {},
             'smallest': None}
    inside = dict(empty, in_region=True, expressing=['IndexArgmaxDiff'], completions={'IndexArgmaxDiff': 10230692},
                  smallest={'name': 'IndexArgmaxDiff', 'completions': 10230692})
    return {'blueprints_file': 'blueprints.json', 'formulas': {'A1': empty, 'A2': empty, 'A3': empty, 'A4': inside}}


def write_formulas(root):
    folder = root / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'planted_formulas.json').write_text(json.dumps(formulas_json()))
    (folder / 'coverage.json').write_text(json.dumps(coverage_json()))
    (folder / 'segments.json').write_text(json.dumps(TINY.to_dict()))
    return folder


def write_rq1(root, near_last=NEAR_100K):
    """The four tables of `rq1 summary`, produced by the real writers from synthetic checkpoints."""
    folder = write_formulas(root)
    checkpoints = checkpoint_frame(near_last)
    checkpoints.to_csv(folder / 'checkpoints.csv', index=False)
    rq.summarize_checkpoints(checkpoints).to_csv(folder / 'summary.csv', index=False)
    rq.primary_tests(checkpoints).to_csv(folder / 'primary_tests.csv', index=False)
    rq.detection_thresholds(checkpoints).to_csv(folder / 'detection_thresholds.csv', index=False)
    rq.first_touch_table(checkpoints).to_csv(folder / 'first_touch.csv', index=False)
    return folder


def write_comparison(root, rows=None):
    folder = root / 'walkforward'
    folder.mkdir(parents=True, exist_ok=True)
    rows = rows or [
        {'config': 'mcts_only', 'n_days': 877, 'sharpe_reference': 0.80, 'sharpe_config': 0.30, 'difference': 0.50,
         'ci_low': -0.40, 'ci_high': 1.30, 'rho': 0.55},
        {'config': 'buy_hold', 'n_days': 877, 'sharpe_reference': 0.80, 'sharpe_config': -0.20, 'difference': 1.00,
         'ci_low': 0.20, 'ci_high': 1.90, 'rho': 0.10}]
    pd.DataFrame(rows, columns=['config', 'n_days', 'sharpe_reference', 'sharpe_config', 'difference', 'ci_low',
                                'ci_high', 'rho']).to_csv(folder / 'comparison.csv', index=False)


def write_blueprint_set(root):
    path = root / web_method.BLUEPRINT_SET
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(BLUEPRINTS))


@pytest.fixture
def results(tmp_path):
    write_rq1(tmp_path)
    write_comparison(tmp_path)
    write_blueprint_set(tmp_path)
    return tmp_path


@pytest.fixture
def client(results):
    return TestClient(web_app.create_app(str(results)))


ALL_PAGES = ['/', '/data', '/method', '/results/planted', '/results/planted/illustration', '/results/placebo',
             '/results/rq1', '/results/walkforward', '/system']
CHAPTER_PAGES = ['/results/planted', '/results/placebo', '/results/rq1', '/results/walkforward']


@pytest.mark.parametrize('url', ALL_PAGES)
def test_every_page_renders(client, url):
    assert client.get(url).status_code == 200


@pytest.mark.parametrize('url', ALL_PAGES)
def test_pages_render_without_result_folder(tmp_path, url):
    page = TestClient(web_app.create_app(str(tmp_path))).get(url)
    assert page.status_code == 200
    assert 'nan' not in page.text.lower().replace('nhận', '').replace('finance', '') or url == '/system'


def test_pipeline_redirects_to_method(client):
    response = client.get('/pipeline', follow_redirects=False)
    assert response.status_code in (302, 307) and response.headers['location'] == '/method'


# --------------------------------------------------------------------------- shared statistics


def test_web_and_runner_share_the_stats_helpers():
    assert web_planted.wilson_interval is st.wilson_interval and rq.wilson_interval is st.wilson_interval
    assert web_planted.fisher_p_greater is st.fisher_p_greater and rq.fisher_p_greater is st.fisher_p_greater
    assert rq.detection_threshold is st.detection_threshold and thesis.FISHER_ALPHA == st.FISHER_ALPHA


# --------------------------------------------------------------------------- planted chapter (RQ2)


def test_planted_page_with_only_the_signals_shows_the_rest_pending(tmp_path):
    write_formulas(tmp_path)           # what the results folder holds before any search has run
    page = TestClient(web_app.create_app(str(tmp_path))).get('/results/planted')
    text = page.text.replace('&#39;', "'")
    assert page.status_code == 200
    for label in ('Bảng 4.1', 'Bảng 4.2', 'Bảng 4.3', 'Hình 4.1', 'RQ2'):
        assert label in text
    assert 'ts_mean(' in text and 'kinh điển' in text and 'lạ (sinh ngẫu nhiên)' in text
    assert text.count('main.py rq1 search') == 3              # the three result items say what to run
    assert 'Giá trị hiện tại: chưa có' in text.replace('</b>', '').replace('<b>', '')
    assert 'Traceback' not in text and 'nan' not in text.lower().replace('nhận', '')


def test_signals_table_reads_type_operators_crowding_and_adf(tmp_path):
    write_formulas(tmp_path)
    rows = {r['name']: r for r in web_planted.read_formulas(str(tmp_path / FOLDER))}
    assert set(rows) == {'A1', 'A2', 'A3', 'A4'}
    assert rows['A1']['kind'] == 'classical' and rows['A3']['kind'] == 'random'
    assert rows['A2']['crowding_share'] == pytest.approx(0.004) and rows['A4']['adf_p'] == pytest.approx(4e-6)
    assert rows['A1']['n_operators'] == 2          # the stored tree is the mean-reversion fixture
    reading = thesis.reading_signals(list(rows.values()))
    assert '2 tín hiệu kinh điển (A1, A2) và 2 tín hiệu lạ (A3, A4)' in reading
    assert 'độ đông cao nhất là 0.80% (A4)' in reading and 'p ADF lớn nhất là 4e-06 (A4)' in reading


def test_planted_page_never_mentions_the_history_of_the_signals(client):
    text = client.get('/results/planted').text
    for word in ('thay', 'trượt', 'planted_window1', 'một lần', 'reward_mode', 'soft', 'gated'):
        assert word not in text.replace('thay đổi', '')


def test_detection_threshold_is_computed_from_fixture_counts(client, results):
    p_a1 = {ic: fisher_exact([[k, 10 - k], [0, 10]], alternative='greater')[1] for ic, k in ((0.05, 2), (0.1, 6))}
    assert p_a1[0.05] == pytest.approx(0.2368, abs=1e-4) and p_a1[0.1] == pytest.approx(0.0054, abs=1e-4)
    detection = {r['a']: r for r in web_planted.read_detection(str(results / FOLDER))}
    assert detection['A1']['threshold_ic'] == 0.1 and detection['A1']['p_fisher'] == pytest.approx(p_a1[0.1])
    assert detection['A3']['threshold_ic'] == 0.1
    assert detection['A2']['threshold_ic'] is None and detection['A4']['threshold_ic'] is None
    assert detection['A1']['rates'] == 'IC 0: 0/10; IC 0.05: 2/10; IC 0.1: 6/10'
    text = client.get('/results/planted').text
    assert 'A1: IC 0.1 (p = 0.005)' in text and 'A2: chưa xác định' in text
    reading = thesis.reading_detection(list(detection.values()))
    assert '2/4 tín hiệu có ngưỡng phát hiện' in reading and 'Đọc:' in reading


def test_near_table_has_wilson_bounds_and_p_against_ic_zero(client, results):
    rows = web_planted.near_rows_with_p(web_planted.near_rows(web_planted.read_summary(str(results / FOLDER))))
    a1 = {r['ic']: r for r in rows if r['a'] == 'A1'}
    assert (a1[0.1]['near_count'], a1[0.1]['n_runs']) == (6, 10) and a1[0.1]['rate'] == pytest.approx(0.6)
    assert (a1[0.1]['low'], a1[0.1]['high']) == st.wilson_interval(6, 10)
    assert a1[0.0]['p_fisher'] is None and a1[0.1]['p_fisher'] == pytest.approx(0.0054, abs=1e-4)
    assert all(r['n_runs'] == 10 for r in rows) and len(rows) == 12       # 4 A x 3 IC at the 100,000 budget
    text = client.get('/results/planted').text
    assert '6/10' in text and '0.60' in text and '0.31 – 0.83' in text
    assert 'A1 ở IC 0.1: 6/10' in text
    assert 'c-near-A1' in text and 'c-near-A4' in text and 'chart-data' in text


def test_near_chart_points_are_json_safe(results):
    chart = web_planted.near_chart(web_planted.near_rows(web_planted.read_summary(str(results / FOLDER))))
    assert set(chart) == {'A1', 'A2', 'A3', 'A4'} and [p[0] for p in chart['A1']] == [0.0, 0.05, 0.1]
    json.dumps(chart)


def test_planted_ignores_the_old_one_shot_folder(tmp_path):
    write_formulas(tmp_path)
    old = tmp_path / 'planted_window1'
    old.mkdir()
    pd.DataFrame([{'strength': 0.1, 'seed': 1, 'near': True, 'exact': True, 'oos_sharpe': 9.87}]).to_csv(old / 'runs.csv', index=False)
    (old / 'planted_formula.json').write_text('{"expression": "OLD_ONE_SHOT_FORMULA"}')
    text = TestClient(web_app.create_app(str(tmp_path))).get('/results/planted').text
    assert 'OLD_ONE_SHOT_FORMULA' not in text and '9.87' not in text and 'planted_window1' not in text


def test_illustration_picks_a_signal_and_reads_the_rq1_folder(client, results, monkeypatch):
    runs = pd.DataFrame([{'config': 'llm_mcts', 'ic': ic, 'formula': 'A1', 'seed': seed}
                         for ic in (0.0, 0.05) for seed in (1, 2)])
    runs.to_csv(results / FOLDER / 'runs.csv', index=False)
    rng = np.random.default_rng(0)
    index = pd.date_range('2020-01-01 09:00', periods=400, freq='1h')
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.003, len(index)))
    base = pd.DataFrame({'Open': close, 'High': close * 1.002, 'Low': close * 0.998, 'Close': close,
                         'Volume': rng.uniform(1000, 5000, len(index))}, index=index)
    formula = mean_reversion_formula()
    seen_segments = []
    monkeypatch.setattr(planted_run, 'load_base', lambda segments: seen_segments.append(segments) or base)
    key = planted_run.calibration_key(base, 0.05, formula, TINY)
    (results / FOLDER / 'calibration.json').write_text(json.dumps({key: {'beta': 0.02}}))
    calls = []
    real_build = planted_run.build_planted_data

    def spy(base_frame, search_end, strength, seed, beta, formula_arg):
        calls.append((search_end, strength, seed, beta))
        return real_build(base_frame, search_end, strength, seed, beta, formula_arg)

    monkeypatch.setattr(planted_run, 'build_planted_data', spy)
    monkeypatch.setattr(web_app, '_planted_equity', lambda data, f, seed, mode: {
        'curve': pd.Series(np.linspace(1e9, 1.1e9, 20), index=data.evaluation.index[:20]),
        'z': 1.0, 'direction': 1.0, 'sharpe': 0.5, 'trades': 7})

    page = client.get('/results/planted/illustration?a=A2&strength=0.05&seed=2')
    assert page.status_code == 200 and seen_segments == [TINY]
    assert calls == [(TINY.search_end, 0.05, 2, 0.02), (TINY.search_end, 0.0, 2, 0.0)]
    assert 'c-equity' in page.text and 'c-prices' in page.text and thesis.ILLUSTRATION_TITLE in page.text
    assert 'Tín hiệu A2' in page.text

    (results / FOLDER / 'calibration.json').write_text('{}')      # not calibrated: a message, and nothing is written
    page = client.get('/results/planted/illustration?strength=0.05&seed=2')
    assert 'hiệu chỉnh' in page.text and 'c-prices' not in page.text
    assert (results / FOLDER / 'calibration.json').read_text() == '{}'


@pytest.mark.parametrize('query', ['?strength=0.03&seed=1', '?strength=0.05&seed=99', '?a=A9&strength=0.05&seed=1'])
def test_illustration_unknown_selection_gives_404(client, results, query):
    pd.DataFrame([{'config': 'llm_mcts', 'ic': 0.05, 'formula': 'A1', 'seed': 1}]).to_csv(results / FOLDER / 'runs.csv', index=False)
    assert client.get('/results/planted/illustration' + query).status_code == 404


def test_removed_routes_are_gone(client):
    for url in ('/planted', '/planted/planted_window1', '/api/planted/progress', '/api/planted/charts'):
        assert client.get(url).status_code == 404


# --------------------------------------------------------------------------- RQ1 chapter


def expected_primary(results):
    """The four primary p-values worked out directly from the fixture counts."""
    classical, odd = ('A1', 'A2'), ('A3', 'A4')
    rows = []
    for budget in (50_000, 100_000):
        for names in (classical, odd):
            def near(config):
                return sum(NEAR_100K[(config, a)][0.1] // (1 if budget == 100_000 else 2) for a in names)
            k1, k2 = near('llm_mcts'), near('mcts_only')
            rows.append(fisher_exact([[k1, 20 - k1], [k2, 20 - k2]], alternative='two-sided')[1])
    return rows, st.holm_adjust(rows)


def test_primary_tests_table_matches_independent_holm(client, results):
    p, holm = expected_primary(results)
    rows = web_rq1.read_primary(str(results / FOLDER))
    assert [(r['budget'], r['a_type']) for r in rows] == [(50_000, 'classical'), (50_000, 'odd'), (100_000, 'classical'),
                                                          (100_000, 'odd')]
    assert [r['p_two_sided'] for r in rows] == pytest.approx(p)
    assert [r['p_holm'] for r in rows] == pytest.approx(holm)
    assert rows[2]['near_llm_mcts'] == 7 and rows[2]['n_llm_mcts'] == 20 and rows[2]['near_mcts_only'] == 3
    text = client.get('/results/rq1').text
    for value in holm:
        assert f"{value:.3f}" in text
    assert 'Bảng 4.4' in text and '50.000 (trước phản hồi)' in text and '7/20' in text and '3/20' in text


def test_primary_reading_says_which_tests_pass_after_holm():
    base = {'a_type': 'classical', 'budget': 50_000, 'near_llm_mcts': 9, 'n_llm_mcts': 20, 'near_mcts_only': 2,
            'n_mcts_only': 20, 'p_two_sided': 0.01, 'p_holm': 0.04}
    none = [dict(base, p_holm=0.2), dict(base, a_type='odd', p_holm=0.5)]
    assert 'Không phép nào có p Holm < 0.05' in thesis.reading_primary(none)
    some = [base, dict(base, a_type='odd', near_llm_mcts=1, near_mcts_only=8, p_holm=0.03)]
    reading = thesis.reading_primary(some)
    assert '2/2 phép có p Holm < 0.05' in reading
    assert 'A kinh điển ở 50.000, LLM + MCTS cao hơn' in reading and 'A lạ ở 50.000, LLM + MCTS thấp hơn' in reading
    assert thesis.primary_value_rq1(some) == 'A kinh điển ở 50.000: p Holm = 0.040; A lạ ở 50.000: p Holm = 0.030'


def test_budget_series_has_wilson_bands_per_config_and_a(results):
    series = web_rq1.budget_series(web_planted.read_summary(str(results / FOLDER)))
    assert list(series) == ['A1', 'A2', 'A3', 'A4'] and list(series['A1']) == ['llm_mcts', 'mcts_only']
    points = series['A1']['llm_mcts']
    assert [p[0] for p in points] == [10_000.0, 50_000.0, 100_000.0]
    assert points[2][1] == pytest.approx(0.6) and (points[2][2], points[2][3]) == pytest.approx(st.wilson_interval(6, 10))
    assert points[1][1] == pytest.approx(0.3)         # 50,000: half of the last budget's count in the fixture
    assert web_rq1.budget_series(pd.DataFrame()) == {}
    reading = thesis.reading_budget(series, 0.1, 50_000)
    assert 'A1: LLM + MCTS 0.30 → 0.60' in reading and 'MCTS không LLM 0.10 → 0.20' in reading


def test_budget_figure_marks_the_end_of_phase_a(client):
    text = client.get('/results/rq1').text
    assert 'Hình 4.3' in text and 'c-budget-A1' in text and 'c-budget-A4' in text
    assert 'hết giai đoạn A, trước phản hồi' in text and '"mark": 50000' in text
    assert 'RQ1' in text


def test_coverage_table_reads_region_and_completions(client, results):
    rows = web_rq1.read_coverage(str(results / FOLDER))
    assert [(r['a'], r['in_region'], r['completions']) for r in rows] == [
        ('A1', False, None), ('A2', False, None), ('A3', False, None), ('A4', True, 10230692)]
    reading = thesis.reading_coverage(rows)
    assert '1/4 A nằm trong vùng' in reading and 'A4 qua `IndexArgmaxDiff`' in reading
    assert '10.230.692 cách điền' in reading and 'A1, A2, A3 nằm ngoài vùng' in reading
    text = client.get('/results/rq1').text
    assert 'Bảng 4.5' in text and '10.230.692' in text and 'ngoài' in text and 'trong' in text


def test_first_touch_table_keeps_touched_over_runs(client, results):
    rows = web_rq1.read_first_touch(str(results / FOLDER))
    cell = next(r for r in rows if (r['config'], r['a'], r['ic']) == ('llm_mcts', 'A1', 0.1))
    assert (cell['n_touched'], cell['n_runs']) == (6, 10)
    assert cell['median_iterations'] == pytest.approx(1750.0) and cell['median_wall_s'] == pytest.approx(35.0)   # seeds 1-6
    none = next(r for r in rows if (r['config'], r['a'], r['ic']) == ('mcts_only', 'A4', 0.1))
    assert none['n_touched'] == 0 and none['median_iterations'] is None
    assert [r['config'] for r in rows if r['a'] == 'A1' and r['ic'] == 0.1] == ['llm_mcts', 'mcts_only']
    reading = thesis.reading_touch(rows)
    assert 'A1: LLM + MCTS chạm 6/10, trung vị 1.750 vòng' in reading and 'MCTS không LLM chạm 0/10' in reading
    text = client.get('/results/rq1').text
    assert 'Bảng 4.6' in text and '6/10' in text


def test_walkforward_comparison_is_descriptive(client, results):
    rows = web_rq1.read_comparison(str(results))
    assert [r['config'] for r in rows] == ['mcts_only', 'buy_hold'] and rows[0]['ci_low'] == pytest.approx(-0.40)
    reading = thesis.reading_walkforward(rows)
    assert 'MCTS không LLM: chênh 0.50 (-0.40 đến 1.30, khoảng chứa 0, ρ = 0.55)' in reading
    assert 'Mua và giữ: chênh 1.00 (0.20 đến 1.90, khoảng không chứa 0, ρ = 0.10)' in reading
    text = client.get('/results/rq1').text
    assert 'Bảng 4.7' in text and '877' in text and '0.55' in text
    assert 'p Fisher' in text            # only the primary table carries p-values
    assert web_rq1.read_comparison(str(results / 'nowhere')) == []


def test_rq1_page_with_only_signals_and_coverage_shows_the_rest_pending(tmp_path):
    write_formulas(tmp_path)           # what the results folder holds before any search has run
    page = TestClient(web_app.create_app(str(tmp_path))).get('/results/rq1')
    text = page.text
    assert page.status_code == 200 and 'Traceback' not in text
    assert 'Bảng 4.5' in text and 'ts_mean(' in text and 'A4' in text         # coverage is filled
    assert text.count('main.py rq1 search') == 3 and 'main.py walkforward real' in text      # primary, figure, first touch
    assert 'Giá trị hiện tại: chưa có' in text.replace('</b>', '').replace('<b>', '')
    rows = {r['label']: r for r in thesis.progress_rows({'coverage': True, 'planted_formulas': True})}
    assert rows['Bảng 4.5']['status'] == 'done' and rows['Bảng 4.4']['status'] == 'none'


def test_rq1_page_without_any_file_is_pending(tmp_path):
    text = TestClient(web_app.create_app(str(tmp_path))).get('/results/rq1').text
    assert text.count('chưa có') >= 5 and 'Traceback' not in text


# --------------------------------------------------------------------------- placebo chapter


def write_walkforward(root, with_real=False, folder='llm_mcts'):
    path = root / 'walkforward' / folder
    path.mkdir(parents=True)
    sharpes = [-0.5, 0.0, 0.2, 1.0]
    rows = [{'mode': 'placebo', 'placebo_set': i + 1, 'n_days': 877, 'n_windows': 7, 'sharpe': v, 'p_value': np.nan}
            for i, v in enumerate(sharpes)]
    if with_real:
        rows.append({'mode': 'real', 'placebo_set': 0, 'n_days': 877, 'n_windows': 7, 'sharpe': 0.5, 'p_value': np.nan})
    pd.DataFrame(rows).to_csv(path / 'summary.csv', index=False)


def test_placebo_page_shows_distribution_and_pending_p(tmp_path):
    write_walkforward(tmp_path)
    text = TestClient(web_app.create_app(str(tmp_path))).get('/results/placebo').text
    assert 'chờ lần chạy thật' in text and 'nan' not in text.lower().replace('nhận', '')
    assert 'lớn nhất 1.00' in text and 'phải lớn hơn 1.00' in text and 'p = 0.20' in text  # 1 / (K + 1), K = 4
    assert text.count('<tr><td>') == 4


def test_placebo_reads_only_the_new_system_folder(tmp_path):
    write_walkforward(tmp_path, folder='oneshot_placebo')            # the old one-shot placebo
    text = TestClient(web_app.create_app(str(tmp_path))).get('/results/placebo').text
    assert 'Sharpe trung bình' not in text and text.count('<tr><td>') == 0 and 'chart-data">null' in text.replace(' ', '')
    assert 'Giá trị hiện tại: chưa có' in text.replace('</b>', '').replace('<b>', '') and 'cần `main.py walkforward placebo`' in text.replace('&#96;', '`')


def test_placebo_p_counts_sets_at_least_as_good_as_real(tmp_path):
    write_walkforward(tmp_path, with_real=True)
    view = web_app.placebo.placebo_view(web_app.placebo.read_summary(str(tmp_path / 'walkforward' / 'llm_mcts')))
    assert view['p'] == pytest.approx(2 / 5)  # real 0.5: only the 1.0 set is at least as good
    assert view['mean'] == pytest.approx(0.175) and view['max'] == 1.0
    assert 'p = 0.400' in thesis.reading_placebo(view)


def test_placebo_p_counts_a_tie_as_at_least_as_good():
    summary = pd.DataFrame({'mode': ['placebo', 'placebo', 'real'], 'placebo_set': [1, 2, 0], 'sharpe': [0.5, 0.1, 0.5]})
    assert web_app.placebo.placebo_view(summary)['p'] == pytest.approx(2 / 3)


def test_placebo_page_without_files_says_missing(tmp_path):
    text = TestClient(web_app.create_app(str(tmp_path))).get('/results/placebo').text
    assert 'chưa có' in text and 'Giá trị hiện tại' in text


def test_system_api_survives_failing_nvidia_smi(client, monkeypatch):
    def broken(*args, **kwargs):
        raise FileNotFoundError('nvidia-smi')
    monkeypatch.setattr(web_system.subprocess, 'run', broken)
    data = client.get('/api/system').json()
    assert {'cpu_percent', 'cpu_per_core', 'ram', 'gpu', 'gpu_error', 'disk'} <= set(data)
    assert data['gpu'] is None and 'FileNotFoundError' in data['gpu_error']
    assert 0.0 <= data['ram']['percent'] <= 100.0 and data['disk']['free_gb'] > 0
    assert client.get('/system').status_code == 200


# --------------------------------------------------------------------------- method chapter


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


def test_blueprint_summary_counts_completions_operators_and_space(tmp_path):
    write_blueprint_set(tmp_path)
    summary = web_method.blueprint_summary(str(tmp_path))
    compiler = SemanticCompiler()
    expected = [count_completions(compiler.compile_blueprint(b['macro_blueprint'])) for b in BLUEPRINTS]
    assert [b['completions'] for b in summary['blueprints']] == expected
    assert summary['count'] == 2 and summary['set_size'] == sum(expected)
    assert summary['grammar_size'] == count_grammar() and summary['set_size'] < summary['grammar_size']
    assert summary['operators_used'] == 6 and summary['operators_total'] == 19      # not_, greater_than, ts_max, ts_mean, sub, ts_min
    assert summary['operators_missing'] and 'ts_min' not in summary['operators_missing']
    assert summary['roots'] == [('not_', 1), ('sub', 1)]
    assert web_method.blueprint_summary(str(tmp_path / 'nowhere')) is None


def test_blueprint_with_a_compile_error_does_not_break_the_page(tmp_path):
    path = tmp_path / web_method.BLUEPRINT_SET
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([BLUEPRINTS[0], {'name': 'Broken', 'macro_blueprint': 'nonsense(?)'}]))
    summary = web_method.blueprint_summary(str(tmp_path))
    assert summary['blueprints'][1]['completions'] is None and summary['set_size'] == summary['blueprints'][0]['completions']
    assert TestClient(web_app.create_app(str(tmp_path))).get('/method').status_code == 200


def test_method_page_shows_set_configs_feedback_and_space_sizes(client):
    html = client.get('/method').text
    for label in ('Bảng 3.1', 'Bảng 3.2', 'Bảng 3.3', 'Bảng 3.4'):
        assert label in html
    summary = web_method.blueprint_summary(str(client.app.state.results_root))
    assert thesis.sci(count_grammar()) in html and thesis.sci(summary['set_size']) in html
    assert f"{summary['operators_used']}/19 toán tử" in html
    for key in ('llm_mcts', 'mcts_only', 'random', 'llm_only', 'buy_hold, tsmom'):
        assert key in html
    plan = BudgetPlan()
    assert 'Giai đoạn A' in html and 'Phản hồi' in html and 'Giai đoạn B' in html and 'Mốc ngân sách' in html
    assert thesis.num(plan.phase_a) in html and thesis.num(plan.total - plan.phase_a) in html


def test_sci_formats_big_integers():
    assert thesis.sci(190409733055739261518522637957499753133894) == '1.9 × 10⁴¹'
    assert thesis.sci(221280682387022) == '2.2 × 10¹⁴' and thesis.sci(10230692) == '1.0 × 10⁷'
    assert thesis.num(100000) == '100.000'


def test_feedback_steps_follow_the_budget_plan():
    plan = BudgetPlan(total=1000, phase_a=400, feedback_blueprints=3, feedback_expressions=4, checkpoints=(400, 1000))
    steps = {s['stage']: s['text'] for s in thesis.feedback_steps(plan, 8)}
    assert '8 blueprint' in steps['Giai đoạn A'] and 'mỗi blueprint 50 vòng' in steps['Giai đoạn A']
    assert '4 biểu thức' in steps['Phản hồi'] and '3 blueprint mới' in steps['Phản hồi']
    assert '600 vòng còn lại' in steps['Giai đoạn B'] and '400, 1.000 vòng' in steps['Mốc ngân sách']
    assert 'Các blueprint' in thesis.feedback_steps(plan, None)[0]['text']


def test_blueprint_summary_reads_roots_only_from_the_rq1_set():
    assert '20261031_rq1' in web_method.BLUEPRINT_SET and '20261029' not in web_method.BLUEPRINT_SET


def test_overview_has_thesis_header_and_progress(client):
    from web import pipeline
    html = client.get('/').text
    assert pipeline.THESIS['title'] in html and pipeline.THESIS['title_vi'] in html
    for question in pipeline.THESIS['rqs']:
        assert question['id'] in html
    for item in thesis.ITEMS:
        assert item['label'] in html


def test_progress_status_follows_availability():
    rows = {r['label']: r for r in thesis.progress_rows({'planted_formulas': True, 'planted_detection': True})}
    assert rows['Bảng 4.1']['status'] == 'done' and rows['Bảng 4.2']['status'] == 'done' and rows['Bảng 4.3']['status'] == 'none'
    rows = {r['label']: r for r in thesis.progress_rows({})}
    assert rows['Bảng 4.1']['status'] == 'none' and rows['Hình 4.2']['status'] == 'none' and rows['Bảng 4.4']['status'] == 'none'


def test_item_labels_are_unique_and_every_item_names_its_rq_or_none():
    labels = [i['label'] for i in thesis.ITEMS]
    assert len(labels) == len(set(labels))
    for item in thesis.ITEMS:
        if item['chapter'].startswith('/results'):
            assert item['rq'] in ('RQ1', 'RQ2', 'RQ1, RQ2')
            assert item.get('role', 'chính') in thesis.ROLE_HELP


def test_overview_progress_follows_the_real_files(client):
    html = client.get('/').text
    text = html[html.index('Tiến độ luận văn'):]
    for label in ('Bảng 4.1', 'Bảng 4.2', 'Bảng 4.3', 'Hình 4.1', 'Bảng 4.4', 'Hình 4.3', 'Bảng 4.5', 'Bảng 4.6',
                  'Bảng 4.7', 'Bảng 3.1'):
        row = text[text.index(label):]
        assert '✅ Xong' in row[:row.index('</tr>')], label
    row = text[text.index('Hình 4.2'):]
    assert 'Chưa có kết quả' in row[:row.index('</tr>')]          # no placebo in the fixture


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
    text = ' '.join(' '.join(n['details']) + n.get('note', '') for n in pipeline.NODES)
    for old in ('planted_window1', 'oneshot', 'ngữ pháp cũ', '20261029'):
        assert old not in text


def test_method_page_draws_walkforward_timeline(tmp_path):
    from strategy_workflows.WalkForward import WINDOWS
    html = TestClient(web_app.create_app(tmp_path)).get('/method').text
    svg = html[html.index('<svg class="gantt"'):html.index('</svg>', html.index('<svg class="gantt"'))]
    for kind in ('train', 'validation', 'eval'):
        assert svg.count(f'class="bar-{kind}"') == 7
    first = WINDOWS[0]
    assert f'{first.search_start} → {first.train_end}' in svg and f'{first.eval_start} → {first.eval_end}' in svg
    assert 'Hình 3.2' in html and 'Bảng 3.1' in html


# --------------------------------------------------------------------------- metric roles


def test_glossary_covers_every_metric_column_shown():
    import re
    from pathlib import Path
    templates = Path(web_app.__file__).parent / 'templates'
    used = set()
    for path in templates.glob('*.html'):
        used |= set(re.findall(r'metric\.(\w+)\.measures', path.read_text(encoding='utf-8')))
    assert used and used <= set(thesis.METRICS)
    for entry in thesis.METRICS.values():
        assert entry['name'] and entry['measures'] and entry['reading'] and entry['role'] in thesis.ROLE_HELP
    for chapter in thesis.PENDING_CHAPTERS.values():
        assert chapter['primary'] in thesis.METRICS and set(chapter['metrics']) <= set(thesis.METRICS)
    for keys in (thesis.PLANTED_METRICS, thesis.RQ1_METRICS, thesis.PLACEBO_METRICS):
        assert set(keys) <= set(thesis.METRICS)
    assert thesis.PLANTED_PRIMARY in thesis.PLANTED_METRICS and thesis.RQ1_PRIMARY in thesis.RQ1_METRICS


@pytest.mark.parametrize('url', CHAPTER_PAGES)
def test_chapter_pages_open_with_primary_metric_box(client, url):
    text = client.get(url).text
    assert 'Chỉ số chính' in text and 'Giá trị hiện tại' in text and 'Chỉ số dùng trong chương này' in text
    assert text.index('Chỉ số chính') < text.index('Chỉ số dùng trong chương này')


@pytest.mark.parametrize('url', CHAPTER_PAGES)
def test_metric_list_rendered_once(client, url):
    assert client.get(url).text.count('Chỉ số dùng trong chương này') == 1


def test_primary_metrics_and_roles_of_the_new_chapters(client):
    planted_text = client.get('/results/planted').text
    assert 'A1: IC 0.1 (p = 0.005)' in planted_text            # primary value: the thresholds, from the data
    rq1_text = client.get('/results/rq1').text
    assert 'role-chính' in rq1_text and 'role-chẩn-đoán' in rq1_text and 'role-phụ' in rq1_text
    assert 'p Holm = ' in rq1_text
    rows = {r['label']: r for r in thesis.progress_rows({})}
    assert rows['Bảng 4.2']['role'] == 'chính' and rows['Bảng 4.3']['role'] == 'phụ'
    assert rows['Bảng 4.4']['role'] == 'chính' and rows['Bảng 4.5']['role'] == 'chẩn đoán'
    roles = {m['key']: m['role'] for m in thesis.metric_rows(thesis.RQ1_METRICS, thesis.RQ1_ROLE_OVERRIDES)}
    assert roles['holm_p'] == 'chính' and roles['wf_sharpe'] == 'phụ'


def test_glossary_states_near_threshold_and_placebo_tag():
    from strategy_workflows.PlantedSignal import NEAR_CORRELATION
    assert f'{NEAR_CORRELATION:g}' in thesis.METRICS['near']['measures']
    assert thesis.ITEM_BY_KEY['placebo_dist']['role'] == 'chính'
