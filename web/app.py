"""
FastAPI app of the read-only thesis web: one page per chapter, plus a machine-resources page.

The app only reads the RQ1 planted-signal folder (planted.THESIS_PLANTED_DIR), the walk-forward folders of the
LLM + MCTS system and the frozen blueprint set under the results root; it never writes there. Prose lives in web/thesis.py, the diagram in web/pipeline.py.
Pages:
    /                               overview and progress table
    /data                           data description
    /method (/pipeline)             main-flow diagram, walk-forward windows, frozen blueprint set
    /results/planted                planted-signal benchmark (RQ2 positive control, RQ1 comparison data)
    /results/planted/illustration   what planting does to prices
    /results/placebo                placebo walk-forward (RQ2, negative control)
    /results/rq1                    role of the LLM (RQ1): primary tests, budget curves, coverage, first touch
    /results/walkforward            chapter without results yet
    /thesis                         thesis PDF: embedded viewer, open and download links
    /thesis/pdf, /thesis/download   the two fixed PDFs (?version=main|nodsr), inline and as attachment
    /system, /api/system            machine resources (tool outside the thesis)
"""

import datetime
import math
import os
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core_engine.BacktestEngine import AlphaBacktestEngine
from core_engine.CalculateMetrics import compute_metrics
from strategy_workflows import RunPlantedSignal as planted_run
from strategy_workflows.MCTSEngine import MCTSEngine, _FixedPositions, describe_candidate
from strategy_workflows.PlantedSignal import PlantedData, PlantedFormula, formula_from_dict
from strategy_workflows.SearchConfigs import BudgetPlan
from utilities.AppConfig import PROJECT_ROOT
from web import charts, method, pipeline, placebo, planted, rq1, thesis
from web.system import read_system

TEMPLATES_DIR = Path(__file__).parent / 'templates'
THESIS_REWARD_MODE = 'sharpe'


def default_results_root() -> str:
    return os.path.join(PROJECT_ROOT, 'results')


def default_thesis_dir() -> str:
    return os.path.join(PROJECT_ROOT, 'docs', 'thesis')


def format_number(value, digits: int = 3) -> str:
    """Fixed-decimals text; a dash for missing or non-finite values."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return '–'
    return '–' if math.isnan(number) or math.isinf(number) else f"{number:.{digits}f}"


def _planted_equity(data: PlantedData, formula: PlantedFormula, seed: int, mode: str) -> Dict:
    """
    Equity on the evaluation segment of the planted formula traded as the oracle does: z-score
    threshold and direction chosen on the search segment, positions computed on the whole frame.
    """
    with planted_run.quiet():
        engine = MCTSEngine(timeframe=planted_run.TIMEFRAME, data=data.search, seed=seed, reward_mode=mode,
                            global_position_matrix=None)
        best = planted_run.score_planted_formula(engine, formula)
        _, direction, _ = engine.evaluate_expression(best['tree'])
    desc = describe_candidate(best['tree'])
    candidate = {'expr': desc['expr'], 'template': desc['template'], 'window': desc['window'],
                 'z_score': desc['z_score_threshold'], 'threshold_upper': desc['threshold_upper'],
                 'threshold_lower': desc['threshold_lower'], 'direction': direction}
    full = data.full.copy()
    full['Volume'] = full['Volume'].fillna(0.0)
    positions = planted_run.candidate_positions(candidate, full)
    evaluation = full.loc[data.evaluation.index]
    result = AlphaBacktestEngine().run(_FixedPositions(positions.loc[evaluation.index]), evaluation)
    metrics = compute_metrics(result)
    return {'curve': result.equity_curve, 'z': best['z'], 'direction': direction,
            'sharpe': metrics.get('sharpe_ratio'), 'trades': metrics.get('total_trades')}


def _load_formula(folder: str, name: str) -> Optional[PlantedFormula]:
    data = planted.read_json(os.path.join(folder, planted.FORMULAS_FILE))
    try:
        return formula_from_dict(data[name]) if isinstance(data, dict) and name in data else None
    except (ValueError, KeyError, TypeError):
        return None


def _illustration_view(folder: str, name: str, strength: float, seed: int) -> Dict:
    """Context of the illustration page; 'message' is set instead of charts when the data cannot be rebuilt."""
    segments = planted.read_segments(folder)
    formula = _load_formula(folder, name)
    if formula is None:
        return {'message': 'Chưa có công thức cài sẵn trong thư mục kết quả luận văn.'}
    base = planted_run.load_base(segments)
    if strength != 0.0:
        key = planted_run.calibration_key(base, strength, formula, segments)
        cache = planted.read_json(os.path.join(folder, 'calibration.json')) or {}
        if key not in cache:
            return {'message': f"Độ mạnh {strength} chưa được hiệu chỉnh trong thư mục kết quả luận văn; "
                               "trang này chỉ đọc nên không hiệu chỉnh thêm."}
    beta = planted_run.get_beta(base, strength, folder, formula, 1, segments)
    data = planted_run.build_planted_data(base, segments.search_end, strength, seed, beta, formula)
    placebo = data if strength == 0.0 else planted_run.build_planted_data(
        base, segments.search_end, 0.0, seed, 0.0, formula)

    boundaries = [(pd.Timestamp(segments.train_end), f"train_end {segments.train_end}"),
                  (pd.Timestamp(segments.search_end), f"search_end {segments.search_end}")]
    view = {
        'message': None, 'formula_expr': formula.expr, 'z_window': formula.z_window,
        'beta': beta, 'ic_search': data.ic_search, 'ic_eval': data.ic_eval,
        'prices': charts.time_series({'giá thật': base['Close'], 'placebo (độ mạnh 0)': placebo.full['Close'],
                                      'giá đã cài': data.full['Close']}),
        'signal': charts.time_series({'s_t': data.signal}, boundaries),
        'equity': None, 'equity_error': None,
    }
    try:
        equity = _planted_equity(data, formula, seed, THESIS_REWARD_MODE)
        view['equity'] = charts.time_series({'công thức đã cài (A)': equity['curve']})
        view['equity_stats'] = {k: charts.clean(equity[k]) for k in ('z', 'direction', 'sharpe', 'trades')}
    except Exception as exc:
        view['equity_error'] = f"{type(exc).__name__}: {exc}"
    return view


def create_app(results_root: Optional[str] = None, thesis_dir: Optional[str] = None) -> FastAPI:
    app = FastAPI(title='Alpha Farm thesis web', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.results_root = str(results_root or default_results_root())
    app.state.thesis_dir = str(thesis_dir or default_thesis_dir())
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters['fmt'] = format_number
    templates.env.filters['inline_code'] = pipeline.format_text
    templates.env.filters['num'] = thesis.num
    templates.env.filters['config_label'] = thesis.config_label

    def folder() -> str:
        return planted.thesis_dir(app.state.results_root)

    def placebo_view() -> Optional[Dict]:
        return placebo.placebo_view(placebo.read_summary(placebo.walkforward_dir(app.state.results_root)))

    def availability() -> Dict[str, bool]:
        summary_ready = not planted.read_summary(folder()).empty
        placebo_now = placebo_view()
        return {'placebo_runs': placebo_now is not None,
                'placebo_real': placebo_now is not None and placebo_now['p'] is not None,
                'planted_formulas': bool(planted.read_formulas(folder())),
                'planted_detection': bool(planted.read_detection(folder())),
                'planted_summary': summary_ready,
                'rq1_primary': bool(rq1.read_primary(folder())),
                'rq1_summary': summary_ready,
                'rq1_touch': bool(rq1.read_first_touch(folder())),
                'coverage': bool(rq1.read_coverage(folder())),
                'wf_comparison': bool(rq1.read_comparison(app.state.results_root)),
                'data': method.data_range() is not None,
                'blueprint_set': method.blueprint_summary(app.state.results_root) is not None}

    def render(request: Request, name: str, active: str, **context) -> HTMLResponse:
        return templates.TemplateResponse(request, name, {'active': active, 'cap': thesis.ITEM_BY_KEY, 'metric': thesis.METRICS, **context})

    @app.get('/', response_class=HTMLResponse)
    def overview(request: Request):
        return render(request, 'overview.html', 'overview', thesis_info=pipeline.THESIS, intro=thesis.OVERVIEW_INTRO,
                      rows=thesis.progress_rows(availability()))

    @app.get('/data', response_class=HTMLResponse)
    def data_page(request: Request):
        return render(request, 'data.html', 'data', intro=thesis.DATA_INTRO, data_range=method.data_range(),
                      windows=method.window_rows(with_bars=True), timeframe=method.TIMEFRAME)

    @app.get('/method', response_class=HTMLResponse)
    def method_page(request: Request):
        blueprint_set = method.blueprint_summary(app.state.results_root)
        steps = thesis.feedback_steps(BudgetPlan(), blueprint_set['count'] if blueprint_set else None)
        return render(request, 'method.html', 'method', **pipeline.build_view(availability()), intro=thesis.METHOD_INTRO,
                      gantt=method.gantt_view(), windows_caption=thesis.WINDOWS_CAPTION, t=thesis, sci=thesis.sci,
                      blueprint_set=blueprint_set, config_rows=thesis.CONFIG_ROWS, feedback_steps=steps,
                      blueprint_reading=thesis.reading_blueprints(blueprint_set) if blueprint_set else '',
                      space_reading=thesis.reading_space(blueprint_set) if blueprint_set else '')

    @app.get('/pipeline')
    def pipeline_redirect():
        return RedirectResponse('/method')

    @app.get('/results/planted', response_class=HTMLResponse)
    def planted_page(request: Request):
        formulas = planted.read_formulas(folder())
        detection = planted.read_detection(folder())
        rows = planted.near_rows_with_p(planted.near_rows(planted.read_summary(folder())))
        seeds = planted.seeds_per_cell(planted.read_summary(folder()))
        return render(
            request, 'planted.html', 'planted', t=thesis, formulas=formulas, detection=detection, rows=rows,
            chart=planted.near_chart(rows), a_kinds=planted.A_KINDS, budget=planted.DETECTION_BUDGET,
            config=planted.DETECTION_CONFIG, primary=thesis.metric_entry(thesis.PLANTED_PRIMARY, seeds),
            primary_value=thesis.primary_value_planted(detection),
            metric_rows=thesis.metric_rows(thesis.PLANTED_METRICS, seeds=seeds), near_definition=thesis.METRICS['near']['measures'],
            readings={'signals': thesis.reading_signals(formulas), 'detection': thesis.reading_detection(detection),
                      'table': thesis.reading_near_table(rows), 'figure': thesis.reading_near_figure(rows)})

    @app.get('/results/planted/illustration', response_class=HTMLResponse)
    def planted_illustration(request: Request, a: Optional[str] = None, strength: Optional[float] = None,
                             seed: Optional[int] = None):
        runs = planted.read_runs(folder())
        names = [f['name'] for f in planted.read_formulas(folder())]
        strengths = planted.present_values(runs, 'ic')
        seeds = [int(s) for s in planted.present_values(runs, 'seed')]
        context = {'title': thesis.ILLUSTRATION_TITLE, 'strengths': strengths, 'seeds': seeds, 'names': names,
                   'a': a, 'strength': strength, 'seed': seed, 'segments': planted.read_segments(folder()).to_dict()}
        if not strengths or not seeds or not names:
            return render(request, 'illustration.html', 'planted',
                          view={'message': thesis.PLANTED_ILLUSTRATION_MISSING}, **context)
        a = names[0] if a is None else a
        strength = strengths[0] if strength is None else strength
        seed = seeds[0] if seed is None else seed
        matched = [s for s in strengths if math.isclose(s, strength, abs_tol=1e-12)]
        if a not in names or not matched or seed not in seeds:
            raise HTTPException(status_code=404, detail='Tín hiệu, IC mục tiêu hoặc seed không có trong kết quả.')
        context.update(a=a, strength=matched[0], seed=seed)
        return render(request, 'illustration.html', 'planted',
                      view=_illustration_view(folder(), a, matched[0], seed), **context)

    @app.get('/results/placebo', response_class=HTMLResponse)
    def placebo_page(request: Request):
        view = placebo_view()
        return render(
            request, 'placebo.html', 'placebo', t=thesis, view=view, chart=placebo.chart_points(view) if view else None,
            primary=thesis.METRICS[thesis.PLACEBO_PRIMARY], primary_value=thesis.primary_value_placebo(view),
            metric_rows=thesis.metric_rows(thesis.PLACEBO_METRICS), reading=thesis.reading_placebo(view),
            p_text=thesis.placebo_p_text(view),
            feedback_reading=thesis.reading_feedback(placebo.read_feedback(placebo.walkforward_dir(app.state.results_root))))

    @app.get('/results/rq1', response_class=HTMLResponse)
    def rq1_page(request: Request):
        summary = planted.read_summary(folder())
        primary_rows = rq1.read_primary(folder())
        series = rq1.budget_series(summary)
        coverage = rq1.read_coverage(folder())
        touch = rq1.read_first_touch(folder())
        comparison = rq1.read_comparison(app.state.results_root)
        mark = BudgetPlan().phase_a
        seeds = planted.seeds_per_cell(summary)
        expressions = {f['name']: f['expression'] for f in planted.read_formulas(folder())}
        return render(
            request, 'rq1.html', 'rq1', t=thesis, primary_rows=primary_rows, series=series, coverage=coverage,
            touch=touch, comparison=comparison, expressions=expressions, ic=rq1.PRIMARY_IC, mark=mark,
            primary=thesis.metric_entry(thesis.RQ1_PRIMARY, seeds), primary_value=thesis.primary_value_rq1(primary_rows),
            metric_rows=thesis.metric_rows(thesis.RQ1_METRICS, thesis.RQ1_ROLE_OVERRIDES, seeds=seeds),
            design=thesis.rq1_design(seeds), feedback_reading=thesis.reading_feedback(rq1.read_feedback(folder())),
            chart={'series': series, 'mark': mark, 'labels': thesis.CONFIG_LABELS},
            budget_rq=thesis.RQ1_BUDGET_RQ.format(ic=rq1.PRIMARY_IC, mark=thesis.num(mark)),
            readings={'primary': thesis.reading_primary(primary_rows),
                      'budget': thesis.reading_budget(series, rq1.PRIMARY_IC, mark),
                      'coverage': thesis.reading_coverage(coverage), 'touch': thesis.reading_touch(touch),
                      'walkforward': thesis.reading_walkforward(comparison)})

    def add_pending_page(key: str) -> None:
        def pending_page(request: Request):
            page = thesis.PENDING_CHAPTERS[key]
            return render(request, 'pending.html', key, page=page, primary=thesis.METRICS[page['primary']],
                          primary_value=thesis.MISSING, metric_rows=thesis.metric_rows(page['metrics']),
                          items=[i for i in thesis.ITEMS if i['chapter'] == '/results/' + key])
        pending_page.__name__ = f'{key}_page'
        app.get('/results/' + key, response_class=HTMLResponse)(pending_page)

    for key in thesis.PENDING_CHAPTERS:
        add_pending_page(key)

    def pdf_response(version: str, disposition: str) -> FileResponse:
        """One of the two fixed PDFs; an unknown version or a missing file is a 404 (no user-supplied path)."""
        entry = thesis.PDF_VERSIONS.get(version)
        path = os.path.join(app.state.thesis_dir, entry['file']) if entry else ''
        if not entry or not os.path.isfile(path):
            raise HTTPException(status_code=404, detail='Chưa có bản PDF này.')
        return FileResponse(path, media_type='application/pdf', content_disposition_type=disposition,
                            filename=entry['download'], headers={'Cache-Control': 'no-cache'})

    @app.get('/thesis', response_class=HTMLResponse)
    def thesis_page(request: Request):
        files = []
        for version, entry in thesis.PDF_VERSIONS.items():
            path = os.path.join(app.state.thesis_dir, entry['file'])
            info = os.stat(path) if os.path.isfile(path) else None
            modified = datetime.datetime.fromtimestamp(info.st_mtime).strftime('%Y-%m-%d %H:%M') if info else None
            files.append({'version': version, 'label': entry['label'], 'ready': info is not None, 'modified': modified,
                          'size': thesis.format_size(info.st_size) if info else None,
                          'stamp': int(info.st_mtime) if info else 0})
        return render(request, 'thesis_pdf.html', 'thesis', t=thesis, files=files)

    @app.get('/thesis/pdf')
    def thesis_pdf(version: str = 'main'):
        return pdf_response(version, 'inline')

    @app.get('/thesis/download')
    def thesis_download(version: str = 'main'):
        return pdf_response(version, 'attachment')

    @app.get('/system', response_class=HTMLResponse)
    def system_page(request: Request):
        return render(request, 'system.html', 'system')

    @app.get('/api/system')
    def system_api():
        return read_system()

    return app


app = create_app()
