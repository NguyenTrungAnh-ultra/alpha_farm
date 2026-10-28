"""Progress / stop hooks of the MCTS search, the reward-gate counter, and idea injection into process_timeframe."""
import json

import pytest

import strategy_workflows.RunMCTS as run_module
from core_engine.BacktestEngine import load_data
from strategy_workflows.MCTSEngine import MCTSEngine
from strategy_workflows.SemanticCompiler import SemanticCompiler

BLUEPRINT = "sub(ts_mean(?), ts_mean(?))"
WINDOW_START, WINDOW_END = '2022-01-01', '2022-06-30'
ITERATIONS = 40
SEED = 3


@pytest.fixture(scope="module")
def window():
    return load_data('60m')[WINDOW_START:WINDOW_END].copy()


def run_search(window, **kwargs):
    engine = MCTSEngine(timeframe='60m', seed=SEED, data=window)
    root = SemanticCompiler().compile_blueprint(BLUEPRINT)
    reason = engine.run_search_from_blueprint(root, n_iterations=ITERATIONS, **kwargs)
    return engine, reason


def leaderboard(engine):
    return [(c['expr'], c['reward']) for c in engine.get_best_candidates()]


def test_callbacks_do_not_change_the_search(window):
    plain, reason_plain = run_search(window)
    snapshots = []
    observed, reason_observed = run_search(
        window, on_progress=snapshots.append, should_stop=lambda: False, progress_interval_s=0)

    assert leaderboard(plain) == leaderboard(observed)
    assert reason_plain == reason_observed == "budget"
    assert len(snapshots) == ITERATIONS + 1  # one per iteration plus the final one


def test_snapshot_keys_and_final_stop_reason(window):
    snapshots = []
    _, reason = run_search(window, on_progress=snapshots.append, progress_interval_s=0)

    keys = {'iteration', 'n_iterations', 'best_reward', 'evaluations', 'failed_evaluations',
            'gated_evaluations', 'elapsed_s'}
    assert all(keys <= set(s) for s in snapshots)
    assert 'stop_reason' not in snapshots[0]
    assert snapshots[-1]['stop_reason'] == reason == "budget"
    assert snapshots[-1]['iteration'] == ITERATIONS
    assert snapshots[-1]['n_iterations'] == ITERATIONS


def test_should_stop_ends_the_loop(window):
    calls = []

    def stop_on_third_call():
        calls.append(1)
        return len(calls) >= 3

    snapshots = []
    _, reason = run_search(window, on_progress=snapshots.append, should_stop=stop_on_third_call,
                           progress_interval_s=0)

    assert reason == "stopped"
    assert len(calls) == 3
    assert snapshots[-1]['stop_reason'] == "stopped"
    assert snapshots[-1]['iteration'] == 3


def test_throttle_limits_callback_rate(window):
    snapshots = []
    run_search(window, on_progress=snapshots.append, progress_interval_s=3600)
    assert len(snapshots) == 1 and snapshots[0]['stop_reason'] == "budget"


def test_gate_counter_adds_up(window):
    engine, _ = run_search(window)
    summary = engine.error_summary()

    passed = summary['evaluations'] - summary['failed_evaluations'] - summary['gated_evaluations']
    assert passed >= 0
    assert summary['gated_evaluations'] > 0, "a short random search on 6 months should hit the gate"
    assert sum(summary['gate_reasons'].values()) == summary['gated_evaluations']
    assert set(summary['gate_reasons']) <= {"too_few_trades", "low_calmar"}
    scored = [c for c in engine.get_best_candidates() if c['reward'] != -10.0]
    assert passed >= len(scored)


# --- process_timeframe: injected ideas vs the ideas folder -------------------------------------

def _prepare_folder(tmp_path, monkeypatch):
    ideas = tmp_path / "results" / "ideas"
    ideas.mkdir(parents=True)
    path = ideas / "folderidea_60m.json"
    path.write_text(json.dumps({"name": "folderidea", "macro_blueprint": BLUEPRINT}))
    monkeypatch.setattr(run_module, 'PROJECT_ROOT', str(tmp_path))
    monkeypatch.setattr(run_module, 'PortfolioManager', lambda: None)
    return ideas, path


def test_injected_ideas_leave_the_folder_alone(window, tmp_path, monkeypatch):
    ideas_dir, path = _prepare_folder(tmp_path, monkeypatch)
    snapshots = []

    run_module.process_timeframe(
        '60m', window, 10, {}, seed=SEED,
        ideas=[{"name": "injected", "macro_blueprint": BLUEPRINT}],
        on_progress=snapshots.append, progress_interval_s=0)

    assert path.exists()
    assert not (ideas_dir / "processed").exists()
    assert snapshots and all(s['idea_name'] == "injected" and s['timeframe'] == '60m' for s in snapshots)
    assert snapshots[-1]['stop_reason'] == "budget"


def test_folder_ideas_are_moved_when_none_given(window, tmp_path, monkeypatch):
    ideas_dir, path = _prepare_folder(tmp_path, monkeypatch)
    assert [i['name'] for i in run_module.load_ideas('60m')] == ["folderidea"]
    assert path.exists(), "load_ideas must not move files"

    run_module.process_timeframe('60m', window, 10, {}, seed=SEED)

    assert not path.exists()
    assert (ideas_dir / "processed" / "folderidea_60m.json").exists()


def test_stop_ends_the_whole_timeframe(window, tmp_path, monkeypatch):
    from core_engine.BacktestEngine import AlphaBacktestEngine
    _prepare_folder(tmp_path, monkeypatch)
    searched = []
    original = MCTSEngine.run_search_from_blueprint

    def spy(self, root, *args, **kwargs):
        searched.append(root)
        return original(self, root, *args, **kwargs)

    def forbidden(self, strategy, df):
        raise AssertionError("replay backtest must not run after a stop")

    monkeypatch.setattr(MCTSEngine, 'run_search_from_blueprint', spy)
    monkeypatch.setattr(AlphaBacktestEngine, 'run', forbidden)

    tf, generated, rejected, successful = run_module.process_timeframe(
        '60m', window, 10, {}, seed=SEED,
        ideas=[{"name": "a", "macro_blueprint": BLUEPRINT}, {"name": "b", "macro_blueprint": BLUEPRINT}],
        should_stop=lambda: True, progress_interval_s=0)

    assert len(searched) == 1
    assert (tf, rejected, successful) == ('60m', 0, [])
    assert generated >= 0


def test_stop_leaves_remaining_folder_files(window, tmp_path, monkeypatch):
    ideas_dir, path = _prepare_folder(tmp_path, monkeypatch)
    second = ideas_dir / "second_60m.json"
    second.write_text(json.dumps({"name": "second", "macro_blueprint": BLUEPRINT}))

    run_module.process_timeframe('60m', window, 10, {}, seed=SEED, should_stop=lambda: True,
                                 progress_interval_s=0)

    assert sum(p.exists() for p in (path, second)) == 1, "only the idea being searched is moved"


def test_injected_ideas_skip_the_duplicate_check(window, tmp_path, monkeypatch):
    _prepare_folder(tmp_path, monkeypatch)
    failed = tmp_path / "results" / "failed"
    failed.mkdir(parents=True)
    (failed / "dup_60m.py").write_text("# failed earlier")
    snapshots = []

    run_module.process_timeframe(
        '60m', window, 10, {}, seed=SEED,
        ideas=[{"name": "dup", "macro_blueprint": BLUEPRINT}],
        on_progress=snapshots.append, progress_interval_s=0)

    assert snapshots and snapshots[-1]['idea_name'] == "dup"


# --- gate reason classification ---------------------------------------------------------------

def _gate_reasons(window, monkeypatch, metrics_per_direction):
    from strategy_workflows.SemanticCompiler import ASTNode
    calls = iter(metrics_per_direction)  # evaluate_expression scores direction +1 first, then -1
    monkeypatch.setattr('strategy_workflows.MCTSEngine.compute_metrics', lambda result: next(calls))
    engine = MCTSEngine(timeframe='60m', seed=SEED, data=window)
    tree = ASTNode(name="normalized_template", children=[
        ASTNode(name="ts_mean", children=[ASTNode(name="pv_close")], window=5),
        ASTNode(name="window", value=5), ASTNode(name="z_score", value=1.0)])
    reward, _, _ = engine.evaluate_expression(tree)
    assert reward == -10.0
    summary = engine.error_summary()
    assert summary['evaluations'] == 1 and summary['gated_evaluations'] == 1
    return summary['gate_reasons']


def test_gate_reason_low_calmar_when_any_direction_has_enough_trades(window, monkeypatch):
    reasons = _gate_reasons(window, monkeypatch, [
        {'total_trades': 5, 'calmar_ratio': 5.0},
        {'total_trades': 30, 'calmar_ratio': 0.5},
    ])
    assert reasons == {"low_calmar": 1}


def test_gate_reason_too_few_trades_when_every_direction_is_short(window, monkeypatch):
    reasons = _gate_reasons(window, monkeypatch, [
        {'total_trades': 5, 'calmar_ratio': 5.0},
        {'total_trades': 5, 'calmar_ratio': 5.0},
    ])
    assert reasons == {"too_few_trades": 1}
