"""
FastAPI app of the read-only thesis web: one page per chapter, plus a machine-resources page.

The app only reads the thesis result folder (planted.THESIS_PLANTED_DIR) and the frozen blueprint set
under the results root; it never writes there. Prose lives in web/thesis.py, the diagram in web/pipeline.py.
Pages:
    /                               overview and progress table
    /data                           data description
    /method (/pipeline)             main-flow diagram, walk-forward windows, frozen blueprint set
    /results/planted                planted-signal positive control (RQ2)
    /results/planted/illustration   what planting does to prices
    /results/placebo                placebo walk-forward (RQ2, negative control)
    /results/rq1, /results/walkforward   chapters without results yet
    /system, /api/system            machine resources (tool outside the thesis)
"""

import math
import os
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core_engine.BacktestEngine import AlphaBacktestEngine
from core_engine.CalculateMetrics import compute_metrics
from strategy_workflows import RunPlantedSignal as planted_run
from strategy_workflows.MCTSEngine import MCTSEngine, _FixedPositions, describe_candidate
from strategy_workflows.PlantedSignal import PlantedData, PlantedFormula, formula_from_dict
from utilities.AppConfig import PROJECT_ROOT
from web import charts, method, pipeline, placebo, planted, thesis
from web.system import read_system

TEMPLATES_DIR = Path(__file__).parent / 'templates'
THESIS_REWARD_MODE = 'sharpe'


def default_results_root() -> str:
    return os.path.join(PROJECT_ROOT, 'results')


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


def _load_formula(folder: str) -> Optional[PlantedFormula]:
    data = planted.read_json(os.path.join(folder, planted.FORMULA_FILE))
    try:
        return formula_from_dict(data) if data else None
    except (ValueError, KeyError, TypeError):
        return None


def _illustration_view(folder: str, strength: float, seed: int) -> Dict:
    """Context of the illustration page; 'message' is set instead of charts when the data cannot be rebuilt."""
    segments = planted.read_segments(folder)
    formula = _load_formula(folder)
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


def create_app(results_root: Optional[str] = None) -> FastAPI:
    app = FastAPI(title='Alpha Farm thesis web', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.results_root = str(results_root or default_results_root())
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters['fmt'] = format_number
    templates.env.filters['inline_code'] = pipeline.format_text

    def folder() -> str:
        return planted.thesis_dir(app.state.results_root)

    def placebo_view() -> Optional[Dict]:
        return placebo.placebo_view(placebo.read_summary(placebo.walkforward_dir(app.state.results_root)))

    def availability() -> Dict[str, bool]:
        return {'placebo_runs': placebo_view() is not None,
                'planted_runs': not planted.read_runs(folder()).empty,
                'positions': bool(planted.read_positions(folder())),
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
        return render(request, 'method.html', 'method', **pipeline.build_view(), intro=thesis.METHOD_INTRO,
                      gantt=method.gantt_view(), windows_caption=thesis.WINDOWS_CAPTION,
                      blueprint_set=method.blueprint_summary(app.state.results_root),
                      blueprint_caption=thesis.BLUEPRINT_CAPTION)

    @app.get('/pipeline')
    def pipeline_redirect():
        return RedirectResponse('/method')

    @app.get('/results/planted', response_class=HTMLResponse)
    def planted_page(request: Request):
        runs = planted.read_runs(folder())
        rows = planted.strength_table(runs)
        seed_rows = planted.seed_table(runs)
        positions = planted.position_table(planted.read_positions(folder()))
        threshold = planted.near_threshold()
        chart = {'near': planted.near_chart_points(rows), 'corr': planted.closest_points(seed_rows),
                 'threshold': threshold}
        return render(
            request, 'planted.html', 'planted', t=thesis, rows=rows, seed_rows=seed_rows, positions=positions,
            formula_expr=planted.read_formula_expr(folder()), chart=chart,
            primary=thesis.METRICS[thesis.PLANTED_PRIMARY], primary_value=thesis.primary_value_planted(rows),
            metric_rows=thesis.metric_rows(thesis.PLANTED_METRICS),
            near_definition=thesis.NEAR_DEFINITION.format(threshold=threshold),
            readings={'table': thesis.reading_table(rows), 'near': thesis.reading_near(rows),
                      'corr': thesis.reading_corr(seed_rows, threshold),
                      'positions': thesis.reading_positions(positions)})

    @app.get('/results/planted/illustration', response_class=HTMLResponse)
    def planted_illustration(request: Request, strength: Optional[float] = None, seed: Optional[int] = None):
        runs = planted.read_runs(folder())
        strengths = planted.present_values(runs, 'strength')
        seeds = [int(s) for s in planted.present_values(runs, 'seed')]
        context = {'title': thesis.ILLUSTRATION_TITLE, 'strengths': strengths, 'seeds': seeds,
                   'strength': strength, 'seed': seed, 'segments': planted.read_segments(folder()).to_dict()}
        if not strengths or not seeds:
            return render(request, 'illustration.html', 'planted', view={'message': thesis.PLANTED_MISSING}, **context)
        strength = strengths[0] if strength is None else strength
        seed = seeds[0] if seed is None else seed
        matched = [s for s in strengths if math.isclose(s, strength, abs_tol=1e-12)]
        if not matched or seed not in seeds:
            raise HTTPException(status_code=404, detail='Độ mạnh hoặc seed không có trong kết quả.')
        context.update(strength=matched[0], seed=seed)
        return render(request, 'illustration.html', 'planted',
                      view=_illustration_view(folder(), matched[0], seed), **context)

    @app.get('/results/placebo', response_class=HTMLResponse)
    def placebo_page(request: Request):
        view = placebo_view()
        return render(
            request, 'placebo.html', 'placebo', t=thesis, view=view, chart=placebo.chart_points(view) if view else None,
            primary=thesis.METRICS[thesis.PLACEBO_PRIMARY], primary_value=thesis.primary_value_placebo(view),
            metric_rows=thesis.metric_rows(thesis.PLACEBO_METRICS), reading=thesis.reading_placebo(view),
            p_text=thesis.placebo_p_text(view))

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

    @app.get('/system', response_class=HTMLResponse)
    def system_page(request: Request):
        return render(request, 'system.html', 'system')

    @app.get('/api/system')
    def system_api():
        return read_system()

    return app


app = create_app()
