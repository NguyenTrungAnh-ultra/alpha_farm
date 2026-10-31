"""
LLMOnly
=======
The "LLM without search" configuration of the walk-forward comparison: the LLM writes complete formulas (no `?`,
every rolling window written out) once, without seeing any data; each walk-forward window then scores every
formula on its train segment over the template-parameter grid MCTS uses and keeps the best parameters per formula.

Steps (`main.py llmonly <step>`):
    build   ask the LLM for the formula set (`results/formula_sets/<timestamp>/`: formulas.json + generation.json)

A formula is accepted when it compiles, has no `?`, writes the window of every `ts_*` call as its last argument
(a value of the engine's window ladder at 60m, no other number anywhere), is dimension-valid, fits
`MCTS_MAX_DEPTH` and is not a duplicate of an accepted formula (same rendered expression) or a prompt example.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from strategy_workflows.BlueprintGeneration import (
    LLMAsker, GenerationStats, _finish_stats, create_chat, ollama_model_name, parse_ideas,
)
from strategy_workflows.MCTSDimensions import OPERATOR_REGISTRY, OperatorGroup, TEMPLATE_NODES
from strategy_workflows.MCTSEngine import (
    MCTSEngine, MCTSState, ast_to_code, describe_candidate, find_first_placeholder, find_unimplemented_operator,
    scaled_ladders,
)
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler
from utilities.AppConfig import MCTS_MAX_DEPTH
from utilities.Prompts import FORMULA_EXAMPLES, build_formula_batch_prompt, build_formula_correction_prompt

TIMEFRAME = '60m'
DEFAULT_COUNT = 100
DEFAULT_BATCH = 10
# Batched requests allowed: DEFAULT_COUNT / DEFAULT_BATCH plus top-up requests for rejected or repeated formulas.
MAX_FORMULA_BATCHES = 15
LLM_ONLY_SEED = 20261031
LLM_ONLY_TEMPERATURE = 0.3
FORMULAS_FILE = 'formulas.json'
GENERATION_FILE = 'generation.json'
DEFAULT_OUT_ROOT = os.path.join(PROJECT_ROOT, 'results', 'formula_sets')


class FormulaError(ValueError):
    """A formula refused by `parse_formula`; `kind` is 'invalid', 'duplicate' or 'example'."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class CompleteFormula:
    text: str            # as accepted, in blueprint notation with the windows written out
    template: str        # NORMALIZED, RATIO or BOOLEAN
    expr: str            # expression as the search renders it
    tree: ASTNode        # template-rooted tree: windows set, template parameters still open


def window_ladders(timeframe: str = TIMEFRAME) -> Tuple[List[int], List[int]]:
    """(rolling windows, template z-score windows) the engine offers at `timeframe`."""
    return scaled_ladders(timeframe)


def _is_time_series(node: ASTNode) -> bool:
    meta = OPERATOR_REGISTRY.get(node.name)
    return meta is not None and meta['group'] == OperatorGroup.TIME_SERIES


def _fix_windows(node: ASTNode, periods: Sequence[int]) -> None:
    """Move the trailing integer of every `ts_*` call into `node.window`; any other number is an error."""
    for child in node.children:
        _fix_windows(child, periods)
    constants = [c for c in node.children if c.name == 'Constant']
    if not _is_time_series(node):
        if constants:
            raise FormulaError('invalid', f"`{node.name}` has a number as an argument; numbers are allowed only as "
                                          f"the window of a time-series function (one of {list(periods)})")
        return
    arity = len(OPERATOR_REGISTRY[node.name]['input_dims'])
    series = [c for c in node.children if c.name != 'Constant']
    if len(constants) != 1 or node.children[-1].name != 'Constant':
        raise FormulaError('invalid', f"`{node.name}` needs exactly one window as its LAST argument, "
                                      f"one of {list(periods)}")
    window = constants[0].value
    if isinstance(window, bool) or not isinstance(window, int) or window not in periods:
        raise FormulaError('invalid', f"`{node.name}` window {window!r} is not one of {list(periods)}")
    if len(series) != arity:
        raise FormulaError('invalid', f"`{node.name}` takes {arity} series argument(s) before the window, "
                                      f"got {len(series)}")
    node.window = window
    node.children = series


def _has_hole(node: ASTNode) -> bool:
    return node.name == '?' or any(_has_hole(child) for child in node.children)


def _leaf_depth(node: ASTNode, depth: int) -> int:
    return max([depth] + [_leaf_depth(child, depth + 1) for child in node.children])


def parse_formula(text: str, periods: Optional[Sequence[int]] = None, max_depth: int = MCTS_MAX_DEPTH
                  ) -> CompleteFormula:
    """
    A complete formula in blueprint notation (`sub(pv_close, ts_mean(pv_close, 10))`) as a template-rooted tree.
    Raises `FormulaError` with a message meant to be sent back to the LLM.
    """
    periods = list(periods) if periods is not None else window_ladders()[0]
    text = (text or '').strip()
    if not text:
        raise FormulaError('invalid', 'the formula is empty')
    if '?' in text:
        raise FormulaError('invalid', 'a formula must not contain `?`; write a data field or a sub-formula there')
    try:
        root = SemanticCompiler().compile_blueprint(text)
    except Exception as exc:
        raise FormulaError('invalid', str(exc)) from exc
    body = root.children[0] if root.name in TEMPLATE_NODES else root
    _fix_windows(body, periods)
    if _has_hole(root):
        raise FormulaError('invalid', 'a function has too few series arguments (an argument is missing)')
    unimplemented = find_unimplemented_operator(body)
    if unimplemented is not None:
        raise FormulaError('invalid', f"operator {unimplemented} has no code generation")
    # The numeric body sits under the template node (depth 0); a BOOLEAN root is itself at depth 0.
    if _leaf_depth(body, 0 if body is root else 1) > max_depth:
        raise FormulaError('invalid', f"the formula nests functions deeper than {max_depth - 1} levels; use fewer "
                                      "nested functions")
    template = {'normalized_template': 'NORMALIZED', 'ratio_template': 'RATIO'}.get(root.name, 'BOOLEAN')
    try:
        expr = ast_to_code(body)
    except ValueError as exc:
        raise FormulaError('invalid', str(exc)) from exc
    return CompleteFormula(text=text, template=template, expr=expr, tree=root)


# --------------------------------------------------------------------------- scoring over the template grid


def template_grid(tree: ASTNode, window_search: Sequence[int], periods: Sequence[int],
                  max_depth: int = MCTS_MAX_DEPTH) -> List[ASTNode]:
    """
    Every setting of the open template parameters of `tree`, enumerated through MCTS's own action sets
    (NORMALIZED: z-score window x threshold; RATIO: upper x lower threshold; BOOLEAN: one tree).
    """
    def expand(state: MCTSState) -> List[ASTNode]:
        if state.is_terminal():
            return [state.ast_tree]
        if find_first_placeholder(state.ast_tree).name == '?':
            raise ValueError("formula still has an open `?` slot")
        return [leaf for action in state.get_actions() for leaf in expand(state.apply_action(action))]
    return expand(MCTSState(tree, max_depth, list(window_search), list(periods)))


def score_formulas(engine: MCTSEngine, formulas: Sequence[dict]) -> Dict:
    """
    Score each formula over its template grid on the engine's data and put the best parameter setting of
    each formula (first in grid order on ties) on the engine's leaderboard.
    Returns {'formulas', 'rejected' (formulas that no longer parse), 'evaluations' (grid evaluations)}.
    """
    periods = engine.scaled_periods
    rejected = 0
    before = engine.evaluation_count
    for item in formulas:
        try:
            parsed = parse_formula(item['formula'], periods, engine.max_depth)
        except FormulaError as exc:
            rejected += 1
            print(f"formula {item.get('name')} skipped: {exc}")
            continue
        best = None
        for tree in template_grid(parsed.tree, engine.scaled_window_search, periods, engine.max_depth):
            reward, direction, metrics = engine.evaluate_expression(tree)
            if best is None or reward > best[0]:
                best = (reward, direction, metrics)
        engine.update_leaderboard(parsed.expr, *best)
    return {'formulas': len(formulas), 'rejected': rejected, 'evaluations': engine.evaluation_count - before}


# --------------------------------------------------------------------------- generation


def _clean_name(raw: str, fallback: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_]', '', raw or '') or fallback


def generate_formula_batch(
    asker: LLMAsker, n: int, prompt: str, periods: Sequence[int], accepted: List[Dict[str, str]],
    accepted_exprs: Dict[str, str], seen_names: set, stats: GenerationStats, max_depth: int = MCTS_MAX_DEPTH,
) -> int:
    """
    One request for up to `n` formulas, then at most one correction request for the rejected ones. Accepted
    formulas are appended to `accepted` (`{'name', 'formula'}`) and their expressions to `accepted_exprs`.
    Returns the number accepted by this call. Stats count the ideas of the first reply and every rejection.
    """
    start = len(accepted)
    example_exprs = {parse_formula(text, periods, max_depth).expr: text for text in FORMULA_EXAMPLES}

    def done() -> bool:
        return len(accepted) - start >= n

    def take(idea: dict) -> Optional[str]:
        """Accept the idea if it passes; returns the rejection reason otherwise."""
        try:
            text = idea.get('formula')
            if not isinstance(text, str):
                raise FormulaError('invalid', 'the idea has no `formula` field')
            parsed = parse_formula(text, periods, max_depth)
            if parsed.expr in example_exprs:
                raise FormulaError('example', f"`{text}` is a syntax illustration of the prompt; design your own")
            if parsed.expr in accepted_exprs:
                raise FormulaError('duplicate', f"`{text}` is the same expression as the accepted formula "
                                                f"`{accepted_exprs[parsed.expr]}`")
        except FormulaError as exc:
            if exc.kind == 'example':
                stats.example_copy_rejections += 1
            elif exc.kind == 'duplicate':
                stats.duplicate_rejections += 1
            return str(exc)
        base = _clean_name(idea.get('name'), f"Formula_{len(seen_names) + 1}")
        name, suffix = base, 2
        while name in seen_names:
            name, suffix = f"{base}_{suffix}", suffix + 1
        seen_names.add(name)
        accepted_exprs[parsed.expr] = parsed.text
        accepted.append({'name': name, 'formula': parsed.text})
        print(f"[llmonly] accepted {len(accepted) - start}/{n}: {name}: {parsed.text}")
        return None

    stats.rounds_used += 1
    try:
        ideas = parse_ideas(asker.ask(prompt))
    except Exception as exc:
        print(f"[llmonly] chat error: {exc}")
        ideas = None
    if not ideas:
        return 0
    rejected: List[Tuple[dict, str]] = []
    for idea in ideas:
        stats.ideas += 1
        try:
            parse_formula(idea.get('formula'), periods, max_depth)
            stats.compiled += 1
        except FormulaError:
            pass
        if done():
            continue
        reason = take(idea)
        if reason is not None:
            print(f"[llmonly] rejected ({reason})")
            rejected.append((idea, reason))
    if rejected and not done():
        stats.rounds_used += 1
        failures = [(str(item.get('formula', item)), reason) for item, reason in rejected]
        try:
            corrected = parse_ideas(asker.ask(build_formula_correction_prompt(failures, list(periods)))) or []
        except Exception as exc:
            print(f"[llmonly] chat error during correction: {exc}")
            corrected = []
        for (original, _), fix in zip(rejected, corrected):
            if done():
                break
            reason = take({**original, **fix})
            if reason is not None:
                print(f"[llmonly] still rejected after correction ({reason})")
    return len(accepted) - start


def generate_formula_set(
    chat, total: int = DEFAULT_COUNT, batch: int = DEFAULT_BATCH, options: Optional[dict] = None,
    model: str = 'ollama-local', timeframe: str = TIMEFRAME, max_batches: int = MAX_FORMULA_BATCHES,
    max_depth: int = MCTS_MAX_DEPTH,
) -> Tuple[List[Dict[str, str]], GenerationStats, str]:
    """
    `total` formulas in batched requests of up to `batch`, each followed by at most one correction request.
    Requests after the first list the formulas accepted so far; requests continue (top-up) until `total` are
    accepted or `max_batches` batched requests are spent. Returns (accepted, stats, text of the first prompt).
    """
    periods = window_ladders(timeframe)[0]
    asker = LLMAsker(chat, options, model)
    accepted: List[Dict[str, str]] = []
    accepted_exprs: Dict[str, str] = {}
    seen_names: set = set()
    stats = GenerationStats(n_requested=total)
    started = time.time()
    first_prompt = build_formula_batch_prompt(timeframe, min(batch, total), periods)
    try:
        for _ in range(max_batches):
            need = min(batch, total - len(accepted))
            if need <= 0:
                break
            prompt = build_formula_batch_prompt(timeframe, need, periods, avoid=[f['formula'] for f in accepted])
            generate_formula_batch(asker, need, prompt, periods, accepted, accepted_exprs, seen_names, stats,
                                   max_depth)
    finally:
        _finish_stats(stats, asker, started, accepted)
    return accepted, stats, first_prompt


def verify_formula_set(formulas: Sequence[dict], n: int, timeframe: str = TIMEFRAME) -> List[str]:
    """Problems of a finished set against the criteria (empty list = the set qualifies)."""
    periods = window_ladders(timeframe)[0]
    problems = []
    seen: Dict[str, str] = {}
    for item in formulas:
        try:
            parsed = parse_formula(item['formula'], periods)
        except FormulaError as exc:
            problems.append(f"{item['name']}: {exc}")
            continue
        if parsed.expr in seen:
            problems.append(f"{item['name']}: same expression as {seen[parsed.expr]}")
        seen.setdefault(parsed.expr, item['name'])
    if len(formulas) != n:
        problems.append(f"{len(formulas)} formulas, expected {n}")
    return problems


def load_formula_set(path: str) -> List[Dict[str, str]]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_formula_set(chat, out_dir: str, n: int = DEFAULT_COUNT, batch: int = DEFAULT_BATCH,
                      model: str = 'ollama-local', seed: int = LLM_ONLY_SEED) -> bool:
    """
    Generate the set and write formulas.json + generation.json into `out_dir`, only when the criteria hold
    (`n` formulas, each valid, no duplicate expression). Otherwise nothing is written and False is returned.
    """
    options = {'temperature': LLM_ONLY_TEMPERATURE, 'seed': seed}
    accepted, stats, prompt = generate_formula_set(chat, n, batch, options, model)
    problems = verify_formula_set(accepted, n)
    if problems:
        print("[llmonly] FAILED: the set does not meet the criteria; nothing written.")
        for problem in problems:
            print(f"[llmonly]   - {problem}")
        return False
    os.makedirs(out_dir, exist_ok=True)
    set_path = os.path.join(out_dir, FORMULAS_FILE)
    with open(set_path, 'w', encoding='utf-8') as f:
        json.dump(accepted, f, indent=4, ensure_ascii=False)
    with open(set_path, 'rb') as f:
        set_hash = hashlib.sha256(f.read()).hexdigest()
    record = {
        'model': ollama_model_name(model), 'n': n, 'batch_size': batch, 'seed': seed,
        'temperature': LLM_ONLY_TEMPERATURE, 'timeframe': TIMEFRAME, 'windows': window_ladders()[0],
        'max_depth': MCTS_MAX_DEPTH, 'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'formulas_sha256': set_hash, 'created': datetime.now().isoformat(timespec='seconds'),
        'stats': {k: v for k, v in asdict(stats).items() if k != 'proposed_structures'},
        'criteria': {'open_slots': 0, 'duplicate_expressions': 0, 'windows_from_ladder': True},
    }
    with open(os.path.join(out_dir, GENERATION_FILE), 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    print(f"[llmonly] Wrote {len(accepted)} formulas to {set_path}")
    return True


# --------------------------------------------------------------------------- CLI


def step_build(args) -> None:
    out_dir = args.out_dir or os.path.join(DEFAULT_OUT_ROOT, datetime.now().strftime('%Y%m%d_%H%M%S'))
    if os.path.exists(os.path.join(out_dir, FORMULAS_FILE)):
        raise SystemExit(f"[llmonly] {out_dir}/{FORMULAS_FILE} already exists; choose another --out-dir.")
    chat = create_chat(args.model)
    try:
        ok = build_formula_set(chat, out_dir, args.n, args.batch_size, args.model, args.seed)
    finally:
        if hasattr(chat, 'stop_keepalive'):
            chat.stop_keepalive()
    if not ok:
        raise SystemExit(1)


def add_llm_only_parser(subparsers) -> None:
    parser = subparsers.add_parser('llmonly', help='Formula set of the LLM-only configuration')
    steps = parser.add_subparsers(dest='step', required=True)
    p = steps.add_parser('build', help='Generate the formula set; writes nothing unless every criterion holds')
    p.add_argument('--model', default='ollama-local', choices=['ollama-local', 'ollama-9b'])
    p.add_argument('--n', type=int, default=DEFAULT_COUNT)
    p.add_argument('--batch-size', type=int, default=DEFAULT_BATCH, help='Formulas asked for per request')
    p.add_argument('--seed', type=int, default=LLM_ONLY_SEED, help='Ollama seed of the first request')
    p.add_argument('--out-dir', default=None, help='Default: results/formula_sets/<timestamp>')


def run_llm_only(args) -> None:
    {'build': step_build}[args.step](args)
