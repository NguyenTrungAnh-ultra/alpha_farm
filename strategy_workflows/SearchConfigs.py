"""
SearchConfigs
=============
The three search configurations of the RQ1 comparison, each spending one budget of MCTS iterations (or random
samples) on the train segment and ending in the same top-5 selection (`rank_leaderboard`):

    llm_mcts   frozen blueprints first (phase A), then new blueprints the LLM writes from the best formulas so far
               (phase B, the feedback round)
    mcts_only  MCTS from one open `?` under each of the three templates, no LLM
    random     ramped half-and-half sampling (`RandomSearch`)

Blueprints (or template roots) are run round-robin in chunks, each keeping its own MCTS tree
(`MCTSEngine.start_search` / `continue_search`), so a ranking taken at any budget reflects breadth rather than the
order of the blueprints. At the budgets in `BudgetPlan.checkpoints` the leaderboard as it stands is ranked on
validation and the top-5 recorded; this reads the leaderboard only, so the search itself is unchanged by it.
"""

import hashlib
import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import pandas as pd

from strategy_workflows.BlueprintGeneration import BATCH_REQUEST_TIMEOUT_S, log
from strategy_workflows.MCTSEngine import FIELD_EXPRESSIONS, MCTSEngine, SearchSession
from strategy_workflows.PlantedSignal import TOP_K, Segments, distinct_expressions, parse_expression
from strategy_workflows.RandomSearch import TEMPLATES, random_search, template_root
from strategy_workflows.RunPlantedSignal import rank_leaderboard
from strategy_workflows.SemanticCompiler import SemanticCompiler

SYSTEMS = ('llm_mcts', 'mcts_only', 'random')
CHECKPOINTS = (10_000, 25_000, 50_000, 75_000, 100_000)
# Order of the template roots of the no-LLM MCTS.
MCTS_ONLY_TEMPLATES = ('NORMALIZED', 'BOOLEAN', 'RATIO')
FEEDBACK_VARIANT = 'anon_shapes'


@dataclass(frozen=True)
class BudgetPlan:
    """
    Budget of one run, in MCTS iterations (random search: samples). `phase_a` of `total` goes to the initial
    blueprints, the rest to the feedback blueprints. A search is advanced `chunk` iterations at a time.
    """
    total: int = 100_000
    phase_a: int = 50_000
    chunk: int = 500
    checkpoints: tuple = CHECKPOINTS
    feedback_expressions: int = 10
    feedback_blueprints: int = 10
    feedback_variant: str = FEEDBACK_VARIANT

    def to_dict(self) -> dict:
        data = asdict(self)
        data['checkpoints'] = list(self.checkpoints)
        return data


def split_evenly(total: int, parts: int) -> List[int]:
    """`total` split into `parts` integers that differ by at most 1, larger shares first."""
    if parts <= 0:
        return []
    base, extra = divmod(total, parts)
    return [base + (1 if i < extra else 0) for i in range(parts)]


def llm_seed(run_key: str) -> int:
    """Ollama seed derived from a run key, in [0, 2**31): the same run asks the LLM the same questions."""
    return int.from_bytes(hashlib.sha256(run_key.encode('utf-8')).digest()[:4], 'big') & 0x7FFFFFFF


# --------------------------------------------------------------------------- LLM access in workers


def llm_spec(chat, model_key: str = 'ollama-local') -> dict:
    """What a worker process needs to talk to the same Ollama model as `chat` (picklable)."""
    return {'model_key': model_key, 'name': chat.model, 'host': chat.host}


def create_worker_chat(spec: dict):
    """A client for the already running server and model of `spec`; nothing is started or created."""
    from llm_clients.OllamaClient import OllamaChatClient
    return OllamaChatClient.attach(spec['name'], spec['host'], request_timeout=BATCH_REQUEST_TIMEOUT_S)


# --------------------------------------------------------------------------- feedback text

_FIELD_NAMES = {variable: field_name for field_name, variable in FIELD_EXPRESSIONS.items()}


def _render(node) -> str:
    label, children, extra = node
    if label in _FIELD_NAMES:
        return _FIELD_NAMES[label]
    if label == 'Constant':
        return repr(extra)
    # The window of a `ts_*` call is dropped: blueprints give those operators only their series, and a model shown
    # `ts_mean(pv_close, 10)` copies the two-argument form into blueprints, which do not compile.
    arguments = [_render(child) for child in children]
    return f"{label}({', '.join(arguments)})"


def expression_to_blueprint_text(expr: str) -> str:
    """A leaderboard expression (`(close - ts_mean(close, 10))`) in blueprint notation, windows left out."""
    try:
        return _render(parse_expression(expr))
    except (ValueError, SyntaxError):
        return expr


def feedback_items(engine: MCTSEngine, k: int) -> List[dict]:
    """
    The `k` best distinct expressions of the engine's leaderboard by reward on the data the engine searched
    (its train segment), each as {expression, reward, rank_ic}. Nothing from later segments is involved. Formulas
    that differ only in their windows read the same without them, so only the best of each is kept.
    """
    items, seen = [], set()
    for c in distinct_expressions(engine.get_best_candidates()):
        text = expression_to_blueprint_text(c['expr'])
        if text in seen:
            continue
        seen.add(text)
        items.append({'expression': text, 'reward': float(c['reward']),
                      'rank_ic': float((c.get('metrics') or {}).get('rank_ic', 0.0) or 0.0)})
        if len(items) == k:
            break
    return items


def summarize_feedback(records: Sequence[dict]) -> dict:
    """
    Feedback rounds of a set of runs (the `feedback` dicts of runs.csv; runs of other systems hold `{}` and are
    skipped): {'runs', 'fallbacks', 'reasons', 'rejections', 'rejections_after_correction'}. `reasons` counts the
    fallback runs by `error`; a run recorded before the field existed counts as 'unrecorded'.
    """
    rounds = [r for r in records if r and 'fallback' in r]
    out = {'runs': len(rounds), 'fallbacks': 0, 'reasons': {}, 'rejections': {}, 'rejections_after_correction': {}}
    for record in rounds:
        if record['fallback']:
            out['fallbacks'] += 1
            reason = record.get('error') or 'unrecorded'
            out['reasons'][reason] = out['reasons'].get(reason, 0) + 1
        for name in ('rejections', 'rejections_after_correction'):
            for kind, count in (record.get(name) or {}).items():
                out[name][kind] = out[name].get(kind, 0) + int(count)
    return out


def feedback_summary_lines(summary: dict, prefix: str) -> List[str]:
    """Printable lines of `summarize_feedback`; empty when no run had a feedback round."""
    if not summary['runs']:
        return []

    def counts(values: dict) -> str:
        return ', '.join(f"{k} {v}" for k, v in sorted(values.items(), key=lambda kv: -kv[1])) or 'none'

    share = summary['fallbacks'] / summary['runs']
    return [
        f"{prefix} feedback round: {summary['runs']} runs, {summary['fallbacks']} fell back to the initial blueprints "
        f"({share:.0%})",
        f"{prefix}   fallback reasons: {counts(summary['reasons'])}",
        f"{prefix}   ideas rejected in the first reply: {counts(summary['rejections'])}",
        f"{prefix}   ideas still rejected after correction: {counts(summary['rejections_after_correction'])}",
    ]


def feedback_records(runs: 'pd.DataFrame', key: Sequence[str]) -> List[dict]:
    """The `feedback` dicts of a runs.csv frame, one per run (a rerun of the same run replaces the old row)."""
    if 'feedback' not in runs.columns:
        return []
    runs = runs.drop_duplicates(subset=list(key), keep='last')
    records = []
    for text in runs['feedback'].dropna():
        try:
            records.append(json.loads(text))
        except (TypeError, ValueError):
            continue
    return records


# --------------------------------------------------------------------------- clock and records


class SearchTimer:
    """Wall time of a run minus the time spent on measurement (checkpoint ranking, hooks)."""

    def __init__(self):
        self.started = time.monotonic()
        self.overhead = 0.0

    @contextmanager
    def measuring(self):
        begin = time.monotonic()
        try:
            yield
        finally:
            self.overhead += time.monotonic() - begin

    def elapsed(self) -> float:
        return time.monotonic() - self.started - self.overhead


class BudgetClock:
    """Counts spent budget and fires `on_checkpoint(budget, spent)` for each checkpoint once it is reached."""

    def __init__(self, checkpoints: Sequence[int], on_checkpoint: Callable[[int, int], None],
                 on_chunk: Optional[Callable[[int], None]] = None):
        self.spent = 0
        self._pending = sorted(checkpoints)
        self._on_checkpoint = on_checkpoint
        self._on_chunk = on_chunk

    def tick(self, amount: int) -> None:
        self.spent += amount
        if self._on_chunk is not None:
            self._on_chunk(self.spent)
        while self._pending and self.spent >= self._pending[0]:
            self._on_checkpoint(self._pending.pop(0), self.spent)


@dataclass
class SearchOutcome:
    system: str
    checkpoints: List[dict] = field(default_factory=list)   # budget, iterations, evaluations, wall_s, llm_s, picked
    final: Optional[dict] = None                            # rank_leaderboard result at the end of the budget
    iterations: int = 0
    evaluations: int = 0
    error_summary: dict = field(default_factory=dict)
    stop_reasons: Dict[str, int] = field(default_factory=dict)
    blueprint_errors: int = 0
    wall_s: float = 0.0
    llm_s: float = 0.0
    llm_requests: int = 0
    new_blueprints: List[dict] = field(default_factory=list)
    feedback: dict = field(default_factory=dict)
    random_stats: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- scheduling


def run_round_robin(engine: MCTSEngine, sessions: Sequence[SearchSession], quotas: Sequence[int], chunk: int,
                    clock: BudgetClock, stop_reasons: Dict[str, int]) -> None:
    """
    Advance every session by `chunk` iterations in turn until each has used its quota. Entropy and
    patience stops are off: the whole budget is spent. A session that cannot run (it already stopped) gives up
    its remaining quota.
    """
    remaining = list(quotas)
    while any(r > 0 for r in remaining):
        for i, session in enumerate(sessions):
            if remaining[i] <= 0:
                continue
            before = session.iterations
            reason = engine.continue_search(session, min(chunk, remaining[i]), early_stop=False)
            ran = session.iterations - before
            remaining[i] = remaining[i] - ran if ran > 0 else 0
            if remaining[i] <= 0:
                stop_reasons[reason] = stop_reasons.get(reason, 0) + 1
            if ran > 0:
                clock.tick(ran)


def _start_sessions(engine: MCTSEngine, blueprints: Sequence[dict], outcome: SearchOutcome) -> List[SearchSession]:
    compiler = SemanticCompiler()
    sessions = []
    for bp in blueprints:
        try:
            sessions.append(engine.start_search(compiler.compile_blueprint(bp['macro_blueprint'])))
        except Exception as exc:
            outcome.blueprint_errors += 1
            log(f"blueprint {bp.get('name')} failed: {exc}")
    return sessions


def _feedback_round(engine, plan: BudgetPlan, blueprints, run_key: str, chat, outcome: SearchOutcome,
                    model_key: str) -> List[dict]:
    """Ask the LLM for new blueprints from the best train-segment formulas; records the round in `outcome`."""
    from strategy_workflows.BlueprintGeneration import generate_feedback_blueprints
    items = feedback_items(engine, plan.feedback_expressions)
    info = {'n_scored': len(items), 'prompt_sha256': None, 'n_new': 0, 'fallback': False, 'requests': 0,
            'llm_s': 0.0, 'seed': llm_seed(run_key + '|feedback'), 'error': 'no_scored_formulas' if not items else '',
            'correction_error': '', 'rejections': {}, 'rejections_after_correction': {}}
    new: List[dict] = []
    if items:
        new, stats, prompt = generate_feedback_blueprints(
            chat, plan.feedback_blueprints, items, blueprints, variant=plan.feedback_variant,
            options={'seed': info['seed']}, model=model_key)
        info.update(prompt_sha256=hashlib.sha256(prompt.encode('utf-8')).hexdigest(), n_new=len(new),
                    requests=stats.requests, llm_s=stats.llm_seconds, ideas=stats.ideas, compiled=stats.compiled,
                    with_slot=stats.with_slot, example_copy_rejections=stats.example_copy_rejections,
                    duplicate_rejections=stats.duplicate_rejections, error=stats.error,
                    correction_error=stats.correction_error, rejections=dict(stats.rejections),
                    rejections_after_correction=dict(stats.rejections_after_correction))
        if not new and not info['error']:
            info['error'] = 'all_rejected'
    info['fallback'] = not new
    outcome.feedback = info
    outcome.new_blueprints = new
    outcome.llm_s += info['llm_s']
    outcome.llm_requests += info['requests']
    return new


def run_search(
    system: str, engine: MCTSEngine, search, segments: Segments, plan: BudgetPlan = BudgetPlan(),
    blueprints: Sequence[dict] = (), run_key: str = '', chat=None, model_key: str = 'ollama-local',
    on_chunk: Optional[Callable[[MCTSEngine, int, float], None]] = None,
) -> SearchOutcome:
    """
    Spend `plan.total` on `system` and rank the leaderboard on validation at every checkpoint and at the end.

    `engine` searches the train segment; `search` is the continuous frame up to `segments.search_end` used for
    the validation ranking. `blueprints` (frozen set) and `chat` (an object with `send(prompt, schema=..., options=...)`)
    are needed by `llm_mcts` (`model_key` is the `--model` choice, which decides the request format); `run_key` seeds its
    LLM requests. `on_chunk(engine, spent, wall_s)` runs after every
    chunk (its time is not counted in `wall_s`).
    """
    if system not in SYSTEMS:
        raise ValueError(f"system must be one of {SYSTEMS}, got {system!r}")
    outcome = SearchOutcome(system=system)
    timer = SearchTimer()

    def on_checkpoint(budget: int, spent: int) -> None:
        with timer.measuring():
            picked = rank_leaderboard(engine, search, segments, TOP_K)
        outcome.checkpoints.append({
            'budget': budget, 'iterations': spent, 'evaluations': engine.evaluation_count,
            'failed': engine.failed_evaluation_count, 'wall_s': timer.elapsed(), 'llm_s': outcome.llm_s,
            'llm_requests': outcome.llm_requests, 'picked': picked,
        })

    def chunk_hook(spent: int) -> None:
        if on_chunk is not None:
            with timer.measuring():
                on_chunk(engine, spent, timer.elapsed())

    clock = BudgetClock(plan.checkpoints, on_checkpoint, chunk_hook)
    if system == 'llm_mcts':
        if chat is None:
            raise ValueError("llm_mcts needs a chat client")
        sessions = _start_sessions(engine, blueprints, outcome)
        run_round_robin(engine, sessions, split_evenly(plan.phase_a, len(sessions)), plan.chunk, clock,
                        outcome.stop_reasons)
        new = _feedback_round(engine, plan, blueprints, run_key, chat, outcome, model_key)
        rest = plan.total - clock.spent
        new_sessions = _start_sessions(engine, new, outcome)
        if new_sessions:
            run_round_robin(engine, new_sessions, split_evenly(rest, len(new_sessions)), plan.chunk, clock,
                            outcome.stop_reasons)
        else:
            outcome.feedback['fallback'] = True
            outcome.feedback['error'] = outcome.feedback.get('error') or 'no_session_started'
            run_round_robin(engine, sessions, split_evenly(rest, len(sessions)), plan.chunk, clock,
                            outcome.stop_reasons)
    elif system == 'mcts_only':
        sessions = [engine.start_search(template_root(t)) for t in MCTS_ONLY_TEMPLATES]
        run_round_robin(engine, sessions, split_evenly(plan.total, len(sessions)), plan.chunk, clock,
                        outcome.stop_reasons)
    else:
        outcome.random_stats = random_search(engine, plan.total, plan.chunk, clock.tick)

    outcome.iterations = clock.spent
    outcome.evaluations = engine.evaluation_count
    outcome.error_summary = engine.error_summary()
    outcome.wall_s = timer.elapsed()
    last = outcome.checkpoints[-1] if outcome.checkpoints else None
    if last is not None and last['iterations'] == clock.spent:
        outcome.final = last['picked']
    else:
        outcome.final = rank_leaderboard(engine, search, segments, TOP_K)
    return outcome
