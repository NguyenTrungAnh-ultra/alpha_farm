"""
FastAPI app of the read-only dashboard: planted-signal results and machine resources.

The app only reads `<results_root>/planted*/`; it never writes there. Pages:
    /, /planted             all planted folders, tables and comparison charts
    /planted/{name}         one folder
    /planted/{name}/data    rebuilt placebo / planted data for one (strength, seed)
    /system, /api/system    machine resources
"""

import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core_engine.BacktestEngine import AlphaBacktestEngine
from core_engine.CalculateMetrics import compute_metrics
from strategy_workflows import RunPlantedSignal as planted_run
from strategy_workflows.MCTSEngine import MCTSEngine, _FixedPositions, describe_candidate
from strategy_workflows.PlantedSignal import PlantedData, PlantedFormula, Segments, formula_from_dict
from utilities.AppConfig import PROJECT_ROOT
from web import charts, planted
from web.system import read_system

TEMPLATES_DIR = Path(__file__).parent / 'templates'
FORMULA_FILE = 'planted_formula.json'


def default_results_root() -> str:
    return os.path.join(PROJECT_ROOT, 'results')


def format_number(value, digits: int = 3) -> str:
    """Fixed-decimals text; a dash for missing or non-finite values."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return '–'
    return '–' if math.isnan(number) or math.isinf(number) else f"{number:.{digits}f}"


def _find_formula(root: str, folder: str) -> Optional[tuple]:
    """(formula, folder name) from the first planted folder holding planted_formula.json, this folder first."""
    for name in [os.path.basename(folder)] + [n for n in planted.list_dirs(root) if n != os.path.basename(folder)]:
        path = os.path.join(root, name, FORMULA_FILE)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return formula_from_dict(json.load(f)), name
            except (OSError, ValueError, KeyError):
                continue
    return None


def _folder_view(root: str, name: str) -> Dict:
    """Everything the planted page shows for one folder (tables as plain dicts)."""
    folder = os.path.join(root, name)
    runs = planted.read_runs(folder)
    oracle = planted.read_oracle(folder)
    strengths = planted.strength_table(runs)
    return {
        'info': planted.folder_info(folder),
        'strengths': strengths,
        'strength_rows': strengths.to_dict('records') if not strengths.empty else [],
        'seed_rows': planted.seed_table(runs),
        'oracle': oracle,
        'oracle_columns': list(oracle.columns),
        'oracle_rows': oracle.to_dict('records') if not oracle.empty else [],
    }


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


def _data_view(root: str, name: str, strength: float, seed: int) -> Dict:
    """Context of the data page; 'message' is set instead of charts when the data cannot be rebuilt."""
    folder = os.path.join(root, name)
    segments = planted.read_segments(folder)
    found = _find_formula(root, folder)
    if found is None:
        return {'message': f"Không tìm thấy {FORMULA_FILE} trong các thư mục planted*."}
    formula, formula_dir = found
    base = planted_run.load_base(segments)
    if strength != 0.0:
        key = planted_run.calibration_key(base, strength, formula, segments)
        cache = {}
        try:
            with open(os.path.join(folder, 'calibration.json'), 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except (OSError, ValueError):
            pass
        if key not in cache:
            return {'message': f"Độ mạnh {strength} chưa có trong calibration.json của {name} "
                               f"(công thức lấy từ {formula_dir}); trang này không hiệu chỉnh vì việc đó ghi vào thư mục."}
    beta = planted_run.get_beta(base, strength, folder, formula, 1, segments)
    data = planted_run.build_planted_data(base, segments.search_end, strength, seed, beta, formula)
    placebo = data if strength == 0.0 else planted_run.build_planted_data(
        base, segments.search_end, 0.0, seed, 0.0, formula)

    runs = planted.read_runs(folder)
    mode = planted.run_mode(runs, strength, seed)
    top_exprs: List[str] = []
    if not runs.empty:
        match = runs[np.isclose(runs['strength'], strength) & (runs['seed'] == seed)]
        if not match.empty and 'top_exprs' in match.columns:
            top_exprs = planted._json_list(match['top_exprs'].iloc[-1])

    boundaries = [(pd.Timestamp(segments.train_end), f"train_end {segments.train_end}"),
                  (pd.Timestamp(segments.search_end), f"search_end {segments.search_end}")]
    view = {
        'message': None, 'formula_expr': formula.expr, 'z_window': formula.z_window, 'formula_dir': formula_dir,
        'beta': beta, 'ic_search': data.ic_search, 'ic_eval': data.ic_eval, 'mode': mode, 'top_exprs': top_exprs,
        'prices': charts.time_series({'giá thật': base['Close'], 'placebo (độ mạnh 0)': placebo.full['Close'],
                                      'giá đã cài': data.full['Close']}),
        'signal': charts.time_series({'s_t': data.signal}, boundaries),
        'equity': None, 'equity_error': None,
    }
    try:
        equity = _planted_equity(data, formula, seed, mode)
        view['equity'] = charts.time_series({'công thức đã cài (A)': equity['curve']})
        view['equity_stats'] = {k: charts.clean(equity[k]) for k in ('z', 'direction', 'sharpe', 'trades')}
    except Exception as exc:
        view['equity_error'] = f"{type(exc).__name__}: {exc}"
    return view


def create_app(results_root: Optional[str] = None) -> FastAPI:
    app = FastAPI(title='Alpha Farm dashboard', docs_url=None, redoc_url=None, openapi_url=None)
    app.state.results_root = str(results_root or default_results_root())
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters['fmt'] = format_number

    def folder_or_404(name: str) -> str:
        if planted.resolve_dir(app.state.results_root, name) is None:
            raise HTTPException(status_code=404, detail='Không có thư mục này.')
        return name

    def planted_page(request: Request, only: Optional[str] = None) -> HTMLResponse:
        root = app.state.results_root
        names = [only] if only else planted.list_dirs(root)
        views = {n: _folder_view(root, n) for n in names}
        entries = [{'name': n, 'strengths': views[n]['strengths'], 'oracle': views[n]['oracle']} for n in names]
        return templates.TemplateResponse(request, 'planted.html', {
            'views': views, 'names': names, 'only': only,
            'charts': charts.comparison_data(entries),
            'active': 'planted',
        })

    @app.get('/', response_class=HTMLResponse)
    @app.get('/planted', response_class=HTMLResponse)
    def planted_index(request: Request):
        return planted_page(request)

    @app.get('/planted/{name}', response_class=HTMLResponse)
    def planted_one(request: Request, name: str):
        return planted_page(request, folder_or_404(name))

    @app.get('/planted/{name}/data', response_class=HTMLResponse)
    def planted_data(request: Request, name: str, strength: Optional[float] = None, seed: Optional[int] = None):
        folder_or_404(name)
        folder = os.path.join(app.state.results_root, name)
        runs, oracle = planted.read_runs(folder), planted.read_oracle(folder)
        strengths = planted.present_values(runs, oracle, 'strength')
        seeds = [int(s) for s in planted.present_values(runs, oracle, 'seed')]
        if not strengths or not seeds:
            raise HTTPException(status_code=404, detail='Thư mục chưa có runs.csv / oracle.csv.')
        if strength is None:
            strength = strengths[0]
        if seed is None:
            seed = seeds[0]
        matched = [s for s in strengths if math.isclose(s, strength, abs_tol=1e-12)]
        if not matched or seed not in seeds:
            raise HTTPException(status_code=404, detail='Độ mạnh hoặc seed không có trong kết quả.')
        strength = matched[0]
        view = _data_view(app.state.results_root, name, strength, seed)
        return templates.TemplateResponse(request, 'data.html', {
            'name': name, 'strengths': strengths, 'seeds': seeds, 'strength': strength, 'seed': seed,
            'view': view, 'segments': planted.read_segments(folder).to_dict(), 'active': 'planted',
        })

    @app.get('/system', response_class=HTMLResponse)
    def system_page(request: Request):
        return templates.TemplateResponse(request, 'system.html', {'active': 'system'})

    @app.get('/api/planted/progress')
    def planted_progress():
        """Run counts and running flag of every folder (polled by the planted page)."""
        root = app.state.results_root
        return [planted.folder_info(os.path.join(root, n)) for n in planted.list_dirs(root)]

    @app.get('/api/planted/charts')
    def planted_charts():
        root = app.state.results_root
        entries = []
        for n in planted.list_dirs(root):
            v = _folder_view(root, n)
            entries.append({'name': n, 'strengths': v['strengths'], 'oracle': v['oracle']})
        return charts.comparison_data(entries)

    @app.get('/api/system')
    def system_api():
        return read_system()

    return app


app = create_app()
