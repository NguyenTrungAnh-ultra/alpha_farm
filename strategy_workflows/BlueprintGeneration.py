"""
BlueprintGeneration
===================
LLM blueprint generation with structure checks, a small-batch tuning harness and the real-set builder.

Commands (`main.py blueprints <step>`):
    tune    for each (prompt variant x sampling setting) generate a small batch and write runs.csv
    build   generate the real set with one variant and one setting; write it only if every criterion holds

A blueprint is rejected (and sent back to the model for one correction) when its compiled tree equals a
skeleton shown in the prompt variant or one already accepted in the same set. Trees are compared, not
strings, and the data field that fills a fixed leaf is ignored.
"""

import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import requests

from llm_clients.OllamaClient import SAMPLING_OPTION_NAMES, OllamaReplyError, extract_json
from strategy_workflows.MCTSDimensions import DATA_FIELD_DIMENSIONS
from strategy_workflows.SemanticCompiler import ASTNode, SemanticCompiler, count_slots
from utilities.Prompts import (
    PROMPT_VARIANTS, build_batch_correction_prompt, build_batch_prompt, build_correction_prompt,
    build_feedback_prompt, build_idea_prompt, get_variant, prompt_hash, variant_examples,
)

TIMEFRAME = '60m'
DEFAULT_TUNE_COUNT = 5
DEFAULT_SET_COUNT = 20
DEFAULT_ROUNDS_PER_BLUEPRINT = 4
# Read timeout of a batched request. Ollama serves one request at a time, so with many worker processes a request
# waits behind the others for far longer than its own ~100-300 s; the cap only catches a hung server, not a queue.
BATCH_REQUEST_TIMEOUT_S = 6 * 3600
MAX_BATCH_REQUESTS = 5
INTEGER_OPTIONS = ("top_k", "seed")
RUN_FIELDS = [
    'variant', 'params', 'n_requested', 'n_accepted', 'compile_rate', 'slot_rate', 'example_copy_rejections',
    'duplicate_rejections', 'distinct_structures', 'rounds_used', 'seconds',
]

StructureKey = tuple


def log(message: str) -> None:
    """
    Progress line on stderr. Search workers run with stdout redirected to the null device (`quiet()` in
    RunPlantedSignal), so a `print` from the generation code never reaches the parent's log; stderr is untouched
    by it and flushed here because a redirected stderr may otherwise buffer.
    """
    print(message, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- structure

def structure_key(node: ASTNode) -> StructureKey:
    """
    Nested tuple of a compiled tree: operator names and `?` slots, with every data field as the same
    leaf and constants without their value. Window/threshold slots of the template are part of the tree.
    """
    if node.name in DATA_FIELD_DIMENSIONS:
        return ('FIELD',)
    return (node.name, *(structure_key(child) for child in node.children))


def blueprint_key(blueprint: str) -> StructureKey:
    """Structure key of a blueprint string (the string must compile)."""
    return structure_key(SemanticCompiler().compile_blueprint(blueprint))


def variant_example_keys(variant: str) -> Dict[StructureKey, str]:
    """Structure key -> example text, for every skeleton the variant shows the model."""
    return {blueprint_key(example): example for example in variant_examples(variant)}


class StructureRejection(ValueError):
    """A compilable blueprint refused for its structure; `kind` is 'example' or 'duplicate'."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


# Message fragment -> short label, for counting why ideas are rejected; first match wins.
REJECTION_KINDS = (
    ('Arity mismatch', 'arity'), ('Unknown operator', 'unknown_operator'),
    ('Unknown data field', 'unknown_field'), ('has no `?` slot', 'no_slot'),
    ('Dimensional', 'dimension'), ('Syntax error', 'syntax'), ('depth limit', 'depth'),
    ('no code generation', 'unimplemented_operator'),
)


def rejection_kind(exc: Exception) -> str:
    """Short label of why `check_idea` raised `exc`: 'example', 'duplicate', 'schema', a compiler kind or 'other'."""
    if isinstance(exc, StructureRejection):
        return exc.kind
    if type(exc).__name__ == 'ValidationError':
        return 'schema'
    text = str(exc)
    for fragment, kind in REJECTION_KINDS:
        if fragment in text:
            return kind
    return 'other'


def chat_error_kind(exc: Exception) -> str:
    """Short label of a failed request: 'timeout', 'connection', the reply error kind, or the exception text."""
    if isinstance(exc, OllamaReplyError):
        return exc.kind
    if isinstance(exc, requests.exceptions.Timeout):
        return 'timeout'
    if isinstance(exc, requests.exceptions.ConnectionError):
        return 'connection'
    return f"exception: {type(exc).__name__}: {str(exc)[:80]}"


@dataclass
class GenerationStats:
    n_requested: int = 0
    n_accepted: int = 0
    ideas: int = 0                      # ideas parsed from the first reply of a round
    compiled: int = 0                   # of those, blueprints that compile (before any correction)
    with_slot: int = 0                  # of those, blueprints with at least one `?`
    example_copy_rejections: int = 0
    duplicate_rejections: int = 0
    rounds_used: int = 0
    seconds: float = 0.0
    error: str = ''                     # why the first request gave no ideas (`chat_error_kind`, 'no_json', 'no_ideas')
    correction_error: str = ''          # why the correction request failed, same labels
    rejections: Dict[str, int] = field(default_factory=dict)                    # kind -> count, first reply
    rejections_after_correction: Dict[str, int] = field(default_factory=dict)   # kind -> count, still rejected
    requests: int = 0                   # LLM requests made (batched generation: first replies and corrections)
    llm_seconds: float = 0.0            # time spent waiting for the LLM (batched generation)
    proposed_structures: set = field(default_factory=set)

    @property
    def compile_rate(self) -> float:
        return self.compiled / self.ideas if self.ideas else 0.0

    @property
    def slot_rate(self) -> float:
        return self.with_slot / self.ideas if self.ideas else 0.0

    @property
    def distinct_structures(self) -> int:
        """Distinct skeletons among every slot-bearing compilable proposal, accepted or rejected."""
        return len(self.proposed_structures)

    def row(self, variant: str, params: dict) -> dict:
        return {
            'variant': variant, 'params': json.dumps(params, sort_keys=True), 'n_requested': self.n_requested,
            'n_accepted': self.n_accepted, 'compile_rate': round(self.compile_rate, 4),
            'slot_rate': round(self.slot_rate, 4), 'example_copy_rejections': self.example_copy_rejections,
            'duplicate_rejections': self.duplicate_rejections, 'distinct_structures': self.distinct_structures,
            'rounds_used': self.rounds_used, 'seconds': round(self.seconds, 2),
        }


def check_idea(idea_json: dict, example_keys: Dict[StructureKey, str],
               accepted_keys: Dict[StructureKey, str]) -> Tuple[dict, StructureKey]:
    """
    Validate one LLM idea: schema, compilation, a `?` slot, a code-generation-supported operator, and a
    structure that is neither a prompt example nor an already accepted one. Raises ValueError otherwise.
    """
    from strategy_workflows.GenerateStrategies import validate_idea
    from strategy_workflows.MCTSEngine import find_unimplemented_operator

    idea, root = validate_idea(idea_json)
    unimplemented = find_unimplemented_operator(root)
    if unimplemented is not None:
        raise ValueError(f"operator {unimplemented} has no code generation")
    key = structure_key(root)
    blueprint = idea['macro_blueprint']
    if key in example_keys:
        raise StructureRejection(
            'example',
            f"Blueprint `{blueprint}` has the same structure as the example skeleton `{example_keys[key]}` shown "
            "in the prompt. Do not reuse any example skeleton: change the operators or the nesting so the "
            "skeleton is different.")
    if key in accepted_keys:
        raise StructureRejection(
            'duplicate',
            f"Blueprint `{blueprint}` has the same structure as the accepted blueprint `{accepted_keys[key]}`. "
            "Design a skeleton with different operators or nesting.")
    return idea, key


def verify_set(blueprints: List[Dict[str, str]], variant: str) -> List[str]:
    """Problems of a finished set against the criteria (empty list = the set qualifies)."""
    problems = []
    example_keys = variant_example_keys(variant)
    seen: Dict[StructureKey, str] = {}
    compiler = SemanticCompiler()
    for bp in blueprints:
        text = bp['macro_blueprint']
        try:
            root = compiler.compile_open_blueprint(text)
        except Exception as exc:
            problems.append(f"{bp['name']}: does not compile or has no `?` ({exc})")
            continue
        if count_slots(root) < 1:
            problems.append(f"{bp['name']}: no `?` slot")
        key = structure_key(root)
        if key in example_keys:
            problems.append(f"{bp['name']}: copies example skeleton {example_keys[key]}")
        if key in seen:
            problems.append(f"{bp['name']}: same structure as {seen[key]}")
        seen.setdefault(key, bp['name'])
    return problems


# --------------------------------------------------------------------------- generation loop

def ollama_model_name(model: str) -> str:
    return "qwen3.5:9b" if model == "ollama-9b" else "qwen3.5:4b"


def create_chat(model: str):
    from llm_clients.OllamaClient import OllamaChatClient
    return OllamaChatClient(model=ollama_model_name(model), verbose=True)


def load_variant_experience(variant: str) -> str:
    """Experience log text; an anonymised variant never gets it (the log is free text and could name the market)."""
    if get_variant(variant).anonymised:
        return ""
    from strategy_workflows.GenerateStrategies import load_experience_log
    return load_experience_log()


def _first_attempt_flags(idea_json) -> Tuple[bool, bool]:
    """(compiles, has a `?` slot) of the blueprint in a freshly parsed idea, before any correction."""
    if not isinstance(idea_json, dict) or not isinstance(idea_json.get('macro_blueprint'), str):
        return False, False
    try:
        root = SemanticCompiler().compile_blueprint(idea_json['macro_blueprint'])
    except Exception:
        return False, False
    return True, count_slots(root) >= 1


def generate_set(
    chat, n: int, variant: str = 'current', options: Optional[dict] = None, model: str = 'ollama-local',
    experience: str = '', rounds_per_blueprint: int = DEFAULT_ROUNDS_PER_BLUEPRINT, timeframe: str = TIMEFRAME,
) -> Tuple[List[Dict[str, str]], GenerationStats]:
    """
    Ask `chat` for up to `n` blueprints with the given prompt variant and sampling options.

    Each round makes one request, then at most one correction request when the idea is rejected. The loop
    ends when `n` are accepted, the round budget (`n * rounds_per_blueprint`) is spent, or the model returns
    no JSON three times in a row. A `seed` option is advanced by one per request so a fixed seed does not
    repeat the same reply.
    """
    options = {k: v for k, v in (options or {}).items() if v is not None}
    example_keys = variant_example_keys(variant)
    accepted: List[Dict[str, str]] = []
    accepted_keys: Dict[StructureKey, str] = {}
    seen_names: set = set()
    stats = GenerationStats(n_requested=n)
    started = time.time()
    requests_made = 0
    consecutive_failures = 0
    max_rounds = n * rounds_per_blueprint

    def ask(prompt: str) -> str:
        nonlocal requests_made
        call_options = dict(options)
        if 'seed' in call_options:
            call_options['seed'] += requests_made
        requests_made += 1
        extra = {'schema': 'json'} if model == 'ollama-local' else {}
        if call_options:
            extra['options'] = call_options
        return chat.send(prompt, **extra)

    try:
        for round_num in range(1, max_rounds + 1):
            if len(accepted) >= n:
                break
            stats.rounds_used = round_num
            prompt = build_idea_prompt(
                timeframe=timeframe, existing_strategies=accepted[-20:], round_num=round_num,
                total_rounds=max_rounds, experience=experience, tried_names=list(seen_names)[-20:],
                fsa_forbidden_patterns=[], variant=variant,
            )
            try:
                idea_json = extract_json(ask(prompt))
            except Exception as exc:
                print(f"[blueprints] chat error: {exc}")
                idea_json = None
            if idea_json is None:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    print("[blueprints] Model returned no JSON three times in a row; stopping.")
                    break
                continue
            consecutive_failures = 0
            stats.ideas += 1
            compiles, has_slot = _first_attempt_flags(idea_json)
            stats.compiled += compiles
            stats.with_slot += has_slot

            idea, key = None, None
            for attempt in (1, 2):
                try:
                    idea, key = check_idea(idea_json, example_keys, accepted_keys)
                    print(f"[blueprints] round {round_num} attempt {attempt}: accepted {idea['macro_blueprint']}")
                    break
                except Exception as exc:
                    idea = None
                    if isinstance(exc, StructureRejection):
                        if exc.kind == 'example':
                            stats.example_copy_rejections += 1
                        else:
                            stats.duplicate_rejections += 1
                    print(f"[blueprints] round {round_num} attempt {attempt}: rejected ({exc})")
                    _, proposed_slot = _first_attempt_flags(idea_json)
                    if proposed_slot:
                        stats.proposed_structures.add(blueprint_key(idea_json['macro_blueprint']))
                    if attempt == 2:
                        break
                    failed = {'macro_blueprint': idea_json['macro_blueprint']} \
                        if isinstance(idea_json, dict) and 'macro_blueprint' in idea_json else idea_json
                    try:
                        corrected = extract_json(ask(build_correction_prompt(json.dumps(failed, indent=4), str(exc))))
                    except Exception as chat_exc:
                        print(f"[blueprints] chat error during correction: {chat_exc}")
                        break
                    if not isinstance(corrected, dict) or not isinstance(idea_json, dict):
                        break
                    idea_json = {**idea_json, **corrected}
            if idea is None:
                continue
            stats.proposed_structures.add(key)
            name = re.sub(r'[^a-zA-Z0-9_]', '', idea['name']) or f"Idea_{round_num}"
            if name in seen_names:
                continue
            seen_names.add(name)
            accepted_keys[key] = idea['macro_blueprint']
            accepted.append({'name': name, 'macro_blueprint': idea['macro_blueprint']})
            print(f"[blueprints] accepted {len(accepted)}/{n}: {name}: {idea['macro_blueprint']}")
    finally:
        stats.seconds = time.time() - started
        stats.n_accepted = len(accepted)
    return accepted, stats


# --------------------------------------------------------------------------- batched requests

class LLMAsker:
    """
    Sends prompts to `chat` with fixed sampling options. A `seed` option advances by one per request so a fixed
    seed gives a deterministic sequence of different replies; requests and waiting time are counted.
    """

    def __init__(self, chat, options: Optional[dict] = None, model: str = 'ollama-local',
                 timeout: float = BATCH_REQUEST_TIMEOUT_S):
        self.chat = chat
        chat.request_timeout = timeout
        chat.strict_reply = True                # a cut-off or empty reply is an error, not the thinking text
        self.options = {k: v for k, v in (options or {}).items() if v is not None}
        self.model = model
        self.requests = 0
        self.seconds = 0.0

    def ask(self, prompt: str) -> str:
        call_options = dict(self.options)
        if 'seed' in call_options:
            call_options['seed'] += self.requests
        self.requests += 1
        extra = {'schema': 'json'} if self.model == 'ollama-local' else {}
        if call_options:
            extra['options'] = call_options
        started = time.time()
        try:
            return self.chat.send(prompt, **extra)
        finally:
            self.seconds += time.time() - started


def parse_ideas(text: str) -> Optional[List[dict]]:
    """Idea objects of a batch reply: `{"ideas": [...]}`, a bare list, or one idea object. None when no JSON."""
    if not text:
        return None
    try:
        found = json.loads(text.strip())
    except json.JSONDecodeError:
        found = extract_json(text)
    if isinstance(found, dict):
        found = found['ideas'] if isinstance(found.get('ideas'), list) else [found]
    if not isinstance(found, list):
        return None
    return [item for item in found if isinstance(item, dict)]


def generate_batch(
    asker: LLMAsker, n: int, prompt: str, example_keys: Dict[StructureKey, str],
    accepted: List[Dict[str, str]], accepted_keys: Dict[StructureKey, str], seen_names: set, stats: GenerationStats,
) -> int:
    """
    One request for up to `n` blueprints, then at most one correction request for the rejected ones.

    Each idea is checked with `check_idea` against the prompt examples and everything already in
    `accepted_keys` (earlier ideas of the same reply included). New blueprints are appended to `accepted` and
    their structures to `accepted_keys`. Returns the number accepted by this call. Stats count the ideas of the
    first reply (compile / slot rates before any correction) and every rejection.
    """
    start_accepted = len(accepted)

    def take(idea_json: dict, kinds: Dict[str, int]) -> Optional[str]:
        """Accept the idea if it passes; returns the rejection reason otherwise (its kind is counted in `kinds`)."""
        try:
            idea, key = check_idea(idea_json, example_keys, accepted_keys)
        except Exception as exc:
            kind = rejection_kind(exc)
            kinds[kind] = kinds.get(kind, 0) + 1
            if isinstance(exc, StructureRejection):
                if exc.kind == 'example':
                    stats.example_copy_rejections += 1
                else:
                    stats.duplicate_rejections += 1
            _, proposed_slot = _first_attempt_flags(idea_json)
            if proposed_slot:
                stats.proposed_structures.add(blueprint_key(idea_json['macro_blueprint']))
            return str(exc)
        stats.proposed_structures.add(key)
        base = re.sub(r'[^a-zA-Z0-9_]', '', idea['name']) or f"Idea_{len(seen_names) + 1}"
        name, suffix = base, 2
        while name in seen_names:
            name, suffix = f"{base}_{suffix}", suffix + 1
        seen_names.add(name)
        accepted_keys[key] = idea['macro_blueprint']
        accepted.append({'name': name, 'macro_blueprint': idea['macro_blueprint']})
        log(f"[blueprints] accepted {len(accepted) - start_accepted}/{n}: {name}: {idea['macro_blueprint']}")
        return None

    def done() -> bool:
        return len(accepted) - start_accepted >= n

    stats.rounds_used += 1
    try:
        ideas = parse_ideas(asker.ask(prompt))
        if ideas is None:
            stats.error = 'no_json'
        elif not ideas:
            stats.error = 'no_ideas'
    except Exception as exc:
        stats.error = chat_error_kind(exc)
        log(f"[blueprints] chat error: {stats.error}: {exc}")
        ideas = None
    if not ideas:
        log(f"[blueprints] no ideas from the first request ({stats.error})")
        return 0
    rejected: List[Tuple[dict, str]] = []
    for idea_json in ideas:
        stats.ideas += 1
        compiles, has_slot = _first_attempt_flags(idea_json)
        stats.compiled += compiles
        stats.with_slot += has_slot
        if done():
            continue
        reason = take(idea_json, stats.rejections)
        if reason is not None:
            log(f"[blueprints] rejected ({reason})")
            rejected.append((idea_json, reason))
    if rejected and not done():
        stats.rounds_used += 1
        failures = [(str(item.get('macro_blueprint', item)), reason) for item, reason in rejected]
        try:
            corrected = parse_ideas(asker.ask(build_batch_correction_prompt(failures)))
            if corrected is None:
                stats.correction_error = 'no_json'
            elif not corrected:
                stats.correction_error = 'no_ideas'
            corrected = corrected or []
        except Exception as exc:
            stats.correction_error = chat_error_kind(exc)
            log(f"[blueprints] chat error during correction: {stats.correction_error}: {exc}")
            corrected = []
        for (original, _), fix in zip(rejected, corrected):
            if done():
                break
            reason = take({**original, **fix}, stats.rejections_after_correction)
            if reason is not None:
                log(f"[blueprints] still rejected after correction ({reason})")
    return len(accepted) - start_accepted


def _finish_stats(stats: GenerationStats, asker: LLMAsker, started: float, accepted: list) -> None:
    stats.seconds = time.time() - started
    stats.requests = asker.requests
    stats.llm_seconds = asker.seconds
    stats.n_accepted = len(accepted)


def generate_initial_set(
    chat, total: int = DEFAULT_SET_COUNT, batch: int = 10, variant: str = 'anon_shapes', options: Optional[dict] = None,
    model: str = 'ollama-local', experience: str = '', timeframe: str = TIMEFRAME,
    max_batches: int = MAX_BATCH_REQUESTS,
) -> Tuple[List[Dict[str, str]], GenerationStats]:
    """
    The initial blueprint set in batched requests of up to `batch` ideas, each followed by at most one
    correction request. A request after the first lists the blueprints accepted so far, so the model avoids them,
    and the structure check rejects any that repeat anyway. Requests continue (top-up) until `total` are
    accepted or `max_batches` batched requests are spent. Fewer than `total` accepted is returned as is; the
    caller decides what that means. `stats.requests` counts every request, corrections included.
    """
    asker = LLMAsker(chat, options, model)
    example_keys = variant_example_keys(variant)
    accepted: List[Dict[str, str]] = []
    accepted_keys: Dict[StructureKey, str] = {}
    seen_names: set = set()
    stats = GenerationStats(n_requested=total)
    started = time.time()
    try:
        for _ in range(max_batches):
            need = min(batch, total - len(accepted))
            if need <= 0:
                break
            prompt = build_batch_prompt(timeframe, need, avoid=[bp['macro_blueprint'] for bp in accepted],
                                        variant=variant, experience=experience)
            generate_batch(asker, need, prompt, example_keys, accepted, accepted_keys, seen_names, stats)
    finally:
        _finish_stats(stats, asker, started, accepted)
    return accepted, stats


def generate_feedback_blueprints(
    chat, n: int, scored: List[dict], initial: Sequence[Dict[str, str]], variant: str = 'anon_shapes',
    options: Optional[dict] = None, model: str = 'ollama-local', timeframe: str = TIMEFRAME,
) -> Tuple[List[Dict[str, str]], GenerationStats, str]:
    """
    New blueprints from the best formulas so far: one batched request for `n` ideas (`scored` items hold
    `expression`, `reward`, `rank_ic`) and at most one correction request. A new blueprint must not repeat the
    structure of any `initial` blueprint, a prompt example, or another new one. Returns (new blueprints, stats,
    the feedback prompt text).
    """
    asker = LLMAsker(chat, options, model)
    example_keys = variant_example_keys(variant)
    accepted_keys: Dict[StructureKey, str] = {}
    for bp in initial:
        try:
            accepted_keys.setdefault(blueprint_key(bp['macro_blueprint']), bp['macro_blueprint'])
        except Exception:
            continue
    seen_names = {bp['name'] for bp in initial}
    prompt = build_feedback_prompt(timeframe, n, scored, avoid=[bp['macro_blueprint'] for bp in initial],
                                   variant=variant)
    new: List[Dict[str, str]] = []
    stats = GenerationStats(n_requested=n)
    started = time.time()
    try:
        generate_batch(asker, n, prompt, example_keys, new, accepted_keys, seen_names, stats)
    finally:
        _finish_stats(stats, asker, started, new)
    return new, stats, prompt


# --------------------------------------------------------------------------- sampling settings

def parse_params(text: str) -> dict:
    """'temperature=0.7,top_p=0.9' -> {'temperature': 0.7, 'top_p': 0.9}; '' or 'default' -> {}."""
    text = text.strip()
    if text in ('', 'default'):
        return {}
    params = {}
    for part in text.split(','):
        name, sep, value = part.partition('=')
        name = name.strip()
        if not sep or name not in SAMPLING_OPTION_NAMES:
            raise ValueError(f"Bad sampling setting '{part}': use name=value with name in {SAMPLING_OPTION_NAMES}")
        params[name] = int(value) if name in INTEGER_OPTIONS else float(value)
    return params


def timestamp() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def combo_label(index: int, variant: str) -> str:
    return f"{index:02d}_{variant}"


# --------------------------------------------------------------------------- step: tune

def run_tuning(
    chat, variants: List[str], settings: List[dict], n: int, out_dir: str, model: str = 'ollama-local',
    rounds_per_blueprint: int = DEFAULT_ROUNDS_PER_BLUEPRINT,
) -> pd.DataFrame:
    """One small batch per (variant, setting); runs.csv and one accepted-blueprint JSON per combination."""
    os.makedirs(os.path.join(out_dir, 'accepted'), exist_ok=True)
    rows = []
    index = 0
    for variant in variants:
        experience = load_variant_experience(variant)
        for params in settings:
            index += 1
            print(f"[blueprints] combination {index}: variant={variant} params={params or 'default'}")
            accepted, stats = generate_set(chat, n, variant, params, model, experience, rounds_per_blueprint)
            rows.append(stats.row(variant, params))
            record = {'variant': variant, 'params': params, 'model': ollama_model_name(model),
                      'prompt_sha256': prompt_hash(variant), 'blueprints': accepted}
            with open(os.path.join(out_dir, 'accepted', f"{combo_label(index, variant)}.json"), 'w',
                      encoding='utf-8') as f:
                json.dump(record, f, indent=4, ensure_ascii=False)
            pd.DataFrame(rows, columns=RUN_FIELDS).to_csv(os.path.join(out_dir, 'runs.csv'), index=False)
    return pd.DataFrame(rows, columns=RUN_FIELDS)


def step_tune(args) -> None:
    out_dir = os.path.join(args.out_root, timestamp())
    settings = [parse_params(p) for p in args.params]
    chat = create_chat(args.model)
    try:
        frame = run_tuning(chat, args.variants, settings, args.n, out_dir, args.model, args.rounds_per_blueprint)
    finally:
        if hasattr(chat, 'stop_keepalive'):
            chat.stop_keepalive()
    with pd.option_context('display.width', 200, 'display.max_columns', None):
        print(frame.to_string(index=False))
    print(f"[blueprints] Wrote {os.path.join(out_dir, 'runs.csv')}")


# --------------------------------------------------------------------------- step: build

def build_set(chat, n: int, variant: str, params: dict, model: str, out_dir: str,
              rounds_per_blueprint: int = DEFAULT_ROUNDS_PER_BLUEPRINT, batch_size: int = 0) -> bool:
    """
    Generate the real set and write blueprints.json + generation.json into `out_dir`, but only when the
    set criteria hold: n accepted, 0 example copies, no duplicate structure, every blueprint compiles
    with at least one `?`. Otherwise nothing is written and False is returned. `batch_size` > 0 asks for the
    set in batched requests of that many ideas (`generate_initial_set`) instead of one idea per round.
    """
    experience = load_variant_experience(variant)
    if batch_size > 0:
        accepted, stats = generate_initial_set(chat, n, batch_size, variant, params, model, experience)
    else:
        accepted, stats = generate_set(chat, n, variant, params, model, experience, rounds_per_blueprint)
    problems = verify_set(accepted, variant)
    if len(accepted) < n:
        problems.append(f"only {len(accepted)} of {n} blueprints accepted in {stats.rounds_used} rounds")
    if problems:
        print(f"[blueprints] FAILED: the set does not meet the criteria; nothing written.")
        for problem in problems:
            print(f"[blueprints]   - {problem}")
        return False
    os.makedirs(out_dir, exist_ok=True)
    set_path = os.path.join(out_dir, 'blueprints.json')
    with open(set_path, 'w', encoding='utf-8') as f:
        json.dump(accepted, f, indent=4, ensure_ascii=False)
    with open(set_path, 'rb') as f:
        set_hash = hashlib.sha256(f.read()).hexdigest()
    record = {
        'variant': variant, 'params': params, 'model': ollama_model_name(model), 'n': n, 'batch_size': batch_size,
        'prompt_sha256': prompt_hash(variant), 'blueprints_sha256': set_hash,
        'created': datetime.now().isoformat(timespec='seconds'),
        'stats': {k: v for k, v in asdict(stats).items() if k != 'proposed_structures'}
                 | {'distinct_structures': stats.distinct_structures},
        'criteria': {'example_copies': 0, 'duplicate_structures': 0, 'min_slots': 1},
    }
    with open(os.path.join(out_dir, 'generation.json'), 'w', encoding='utf-8') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    print(f"[blueprints] Wrote {len(accepted)} blueprints to {set_path}")
    return True


def step_build(args) -> None:
    out_dir = args.out_dir or os.path.join(PROJECT_ROOT, 'results', 'blueprint_sets', timestamp())
    if os.path.exists(os.path.join(out_dir, 'blueprints.json')):
        raise SystemExit(f"[blueprints] {out_dir}/blueprints.json already exists; choose another --out-dir.")
    chat = create_chat(args.model)
    try:
        ok = build_set(chat, args.n, args.variant, parse_params(args.params), args.model, out_dir,
                       args.rounds_per_blueprint, args.batch_size)
    finally:
        if hasattr(chat, 'stop_keepalive'):
            chat.stop_keepalive()
    if not ok:
        raise SystemExit(1)


# --------------------------------------------------------------------------- CLI

def add_blueprints_parser(subparsers) -> None:
    parser = subparsers.add_parser('blueprints', help='Tune the blueprint prompt and build the real blueprint set')
    steps = parser.add_subparsers(dest='step', required=True)

    def common(p):
        p.add_argument('--model', default='ollama-local', choices=['ollama-local', 'ollama-9b'])
        p.add_argument('--rounds-per-blueprint', type=int, default=DEFAULT_ROUNDS_PER_BLUEPRINT,
                       help='Round budget is n times this')

    p = steps.add_parser('tune', help='Small batch per (prompt variant x sampling setting)')
    common(p)
    p.add_argument('--variants', nargs='+', default=list(PROMPT_VARIANTS), choices=list(PROMPT_VARIANTS))
    p.add_argument('--params', nargs='+', default=['default'],
                   help="Sampling settings, e.g. default temperature=0.7 temperature=0.5,top_p=0.9,seed=1")
    p.add_argument('--n', type=int, default=DEFAULT_TUNE_COUNT, help='Blueprints per combination')
    p.add_argument('--out-root', default=os.path.join(PROJECT_ROOT, 'results', 'blueprint_tuning'))

    p = steps.add_parser('build', help='Generate the real set; writes nothing unless every criterion holds')
    common(p)
    p.add_argument('--variant', required=True, choices=list(PROMPT_VARIANTS))
    p.add_argument('--params', default='default', help='One sampling setting, e.g. temperature=0.5,top_p=0.9')
    p.add_argument('--n', type=int, default=DEFAULT_SET_COUNT)
    p.add_argument('--batch-size', type=int, default=0,
                   help='Ask for this many blueprints per request (e.g. 10 for 2 requests of 10); 0 = one per round')
    p.add_argument('--out-dir', default=None, help='Default: results/blueprint_sets/<timestamp>')


def run_blueprints(args) -> None:
    {'tune': step_tune, 'build': step_build}[args.step](args)
