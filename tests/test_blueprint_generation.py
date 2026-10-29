import hashlib
import json
import re

import pandas as pd
import pytest

from llm_clients import OllamaClient
from llm_clients.OllamaClient import OllamaChatClient
from strategy_workflows import BlueprintGeneration as BG
from strategy_workflows import GenerateStrategies
from strategy_workflows.SemanticCompiler import SemanticCompiler
from utilities.Prompts import PROMPT_VARIANTS, build_idea_prompt, prompt_hash, variant_examples

MARKET_NAME = re.compile(r"vn30|vietnam|viet nam|\bhose\b|hanoi|ho chi minh", re.IGNORECASE)

NO_SLOT = "sub(ts_mean(pv_high), ts_mean(pv_low))"
EXAMPLE_COPY = "sub(ts_max(?), ts_mean(?))"                  # few-shot example 1 of "current"
EXAMPLE_COPY_OTHER_FIELD = "sub(ts_max(pv_low), ts_min(?))"  # few-shot example 3 with another fixed field
SHAPE_COPY = "mult(ts_sum(?), ts_argmax(?))"                 # shape 1 of "anon_shapes"
ADD_MIN_MAX = "add(ts_min(?), ts_max(?))"
ADD_MIN_MAX_FIELD = "add(ts_min(pv_low), ts_max(?))"
ADD_MIN_MAX_OTHER_FIELD = "add(ts_min(pv_high), ts_max(?))"
SUM_OF_MIN = "ts_sum(ts_min(?))"
RATIO_ROOT = "div(?, ts_sum(?))"
MULT_MIN_MAX = "mult(ts_min(?), ts_max(?))"


def reply(blueprint, name):
    return json.dumps({"name": name, "timeframe": "60m", "family": "volatility-regime",
                       "description": "test", "macro_blueprint": blueprint})


def correction(blueprint):
    return json.dumps({"macro_blueprint": blueprint})


class FakeChat:
    """Stands in for OllamaChatClient: returns queued replies and records prompts and options."""
    model = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.options = []

    def send(self, prompt, schema=None, options=None):
        self.prompts.append(prompt)
        self.options.append(options)
        return self.replies.pop(0) if self.replies else ""

    def stop_keepalive(self):
        pass


@pytest.fixture(autouse=True)
def no_experience_log(monkeypatch):
    monkeypatch.setattr(GenerateStrategies, "load_experience_log", lambda *a, **k: "")


# --- prompt variants --------------------------------------------------------

def test_current_variant_is_the_old_prompt_bit_for_bit():
    plain = dict(timeframe="60m", existing_strategies=[], round_num=1, total_rounds=1)
    rich = dict(timeframe="10m", existing_strategies=[{"name": "A", "timeframe": "10m", "family": "volatility-regime"}],
                round_num=3, total_rounds=20, experience="exp text", tried_names=["x", "y"],
                fsa_forbidden_patterns=["p"])
    # sha256 of build_idea_prompt(**case) computed before the variant argument existed
    assert hashlib.sha256(build_idea_prompt(**plain).encode()).hexdigest() == \
        "36545c6f73e9e9ee38f7e51173dc42c761e9bd62211044bae349475cf9f3c9e5"
    assert hashlib.sha256(build_idea_prompt(**rich).encode()).hexdigest() == \
        "5ed625ea8f89bc664ed5782f4c53abc8fffaca685ecdf18d070c2630c79d4dc1"
    assert build_idea_prompt(**plain, variant="current") == build_idea_prompt(**plain)


@pytest.mark.parametrize("variant", ["anon_rules", "anon_shapes"])
def test_new_variants_hide_the_market(variant):
    prompt = build_idea_prompt("60m", [], 1, 20, variant=variant)
    assert not MARKET_NAME.search(prompt)
    assert "index futures contract" in prompt and "60-minute" in prompt
    assert "`?` is an OPEN SLOT" in prompt and "macro_blueprint" in prompt
    assert prompt_hash(variant) != prompt_hash("current")


def test_current_variant_still_names_the_market():
    assert MARKET_NAME.search(build_idea_prompt("60m", [], 1, 1, variant="current"))


def test_every_variant_example_compiles_with_a_slot_and_is_in_the_prompt():
    compiler = SemanticCompiler()
    for name in PROMPT_VARIANTS:
        prompt = build_idea_prompt("60m", [], 1, 1, variant=name)
        for example in variant_examples(name):
            compiler.compile_open_blueprint(example)
            assert example in prompt


def test_anon_rules_shows_no_formula_example_but_shapes_lists_four():
    rules = build_idea_prompt("60m", [], 1, 1, variant="anon_rules")
    shapes = build_idea_prompt("60m", [], 1, 1, variant="anon_shapes")
    assert "Shape 1" not in rules and "WRONG:" in rules
    assert SHAPE_COPY in shapes and "NEVER output any of these shapes" in shapes


def test_anonymised_variants_refuse_other_timeframes_and_unknown_names_fail():
    with pytest.raises(ValueError, match="60m"):
        build_idea_prompt("10m", [], 1, 1, variant="anon_rules")
    with pytest.raises(ValueError, match="Unknown prompt variant"):
        build_idea_prompt("60m", [], 1, 1, variant="nope")


# --- sampling options -------------------------------------------------------

class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"response": "{}"}


def send_with(monkeypatch, **kwargs):
    seen = {}

    def fake_post(url, json=None, timeout=None):
        seen["payload"] = json
        return FakeResponse()

    monkeypatch.setattr(OllamaClient.requests, "post", fake_post)
    client = OllamaChatClient.__new__(OllamaChatClient)
    client.model, client.host, client.verbose = "m", "http://x", False
    client.send("hi", **kwargs)
    return seen["payload"]


def test_sampling_options_reach_the_payload_only_when_given(monkeypatch):
    assert send_with(monkeypatch)["options"] == {"num_ctx": 16384}
    assert send_with(monkeypatch, options={})["options"] == {"num_ctx": 16384}
    given = {"temperature": 0.7, "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1, "seed": 7}
    assert send_with(monkeypatch, options=given)["options"] == {"num_ctx": 16384, **given}
    partial = send_with(monkeypatch, options={"temperature": 0.0, "top_p": None, "bogus": 1})["options"]
    assert partial == {"num_ctx": 16384, "temperature": 0.0}


def test_generation_passes_options_only_when_given_and_advances_the_seed():
    chat = FakeChat([reply(ADD_MIN_MAX, "A"), reply(SUM_OF_MIN, "B")])
    BG.generate_set(chat, 2, "anon_rules", {"seed": 10, "temperature": 0.5}, model="ollama-9b")
    assert chat.options == [{"seed": 10, "temperature": 0.5}, {"seed": 11, "temperature": 0.5}]
    chat = FakeChat([reply(ADD_MIN_MAX, "A")])
    BG.generate_set(chat, 1, "anon_rules", None, model="ollama-9b")
    assert chat.options == [None]


def test_parse_params():
    assert BG.parse_params("default") == {} and BG.parse_params("") == {}
    assert BG.parse_params("temperature=0.7,top_k=40,seed=3") == {"temperature": 0.7, "top_k": 40, "seed": 3}
    with pytest.raises(ValueError):
        BG.parse_params("mirostat=1")


# --- structure checks -------------------------------------------------------

def test_structure_key_compares_trees_not_strings():
    key = BG.blueprint_key
    assert key(EXAMPLE_COPY_OTHER_FIELD) == key("sub(ts_max(pv_high), ts_min(?))")   # fixed field ignored
    assert key("sub( ts_max(?),ts_mean( ? ) )") == key(EXAMPLE_COPY)                  # spacing ignored
    assert key("sub(ts_max(?), sma(?))") == key(EXAMPLE_COPY)                         # alias compiles to ts_mean
    assert key("sub(ts_max(pv_close), ts_mean(?))") != key(EXAMPLE_COPY)             # a fixed leaf is not a slot
    assert key("sub(ts_mean(?), ts_max(?))") != key(EXAMPLE_COPY)                     # argument order matters


def test_example_copy_is_rejected_with_a_reason_even_with_another_fixed_field():
    examples = BG.variant_example_keys("current")
    for copy in (EXAMPLE_COPY, EXAMPLE_COPY_OTHER_FIELD, "ts_mean(?)"):
        with pytest.raises(BG.StructureRejection, match="example skeleton") as info:
            BG.check_idea(json.loads(reply(copy, "A")), examples, {})
        assert info.value.kind == "example"


def test_duplicate_structure_is_rejected_and_a_distinct_one_accepted():
    examples = BG.variant_example_keys("anon_rules")
    idea, key = BG.check_idea(json.loads(reply(ADD_MIN_MAX_FIELD, "A")), examples, {})
    accepted = {key: idea["macro_blueprint"]}
    with pytest.raises(BG.StructureRejection, match="accepted blueprint") as info:
        BG.check_idea(json.loads(reply(ADD_MIN_MAX_OTHER_FIELD, "B")), examples, accepted)
    assert info.value.kind == "duplicate"
    BG.check_idea(json.loads(reply(ADD_MIN_MAX, "C")), examples, accepted)
    BG.check_idea(json.loads(reply(SUM_OF_MIN, "D")), examples, accepted)


def test_generation_loop_feeds_the_structure_reason_back_and_counts_it():
    replies = [
        reply(SHAPE_COPY, "A"), correction(ADD_MIN_MAX),          # round 1: shape copy, corrected
        reply(ADD_MIN_MAX_OTHER_FIELD, "B"),                          # round 2: fixed leaf, not a slot -> distinct
    ]
    chat = FakeChat(replies)
    accepted, stats = BG.generate_set(chat, 2, "anon_shapes")
    assert [b["macro_blueprint"] for b in accepted] == [ADD_MIN_MAX, ADD_MIN_MAX_OTHER_FIELD]
    assert "example skeleton" in chat.prompts[1]
    assert stats.example_copy_rejections == 1 and stats.duplicate_rejections == 0

    chat = FakeChat([reply(ADD_MIN_MAX_FIELD, "A"), reply(ADD_MIN_MAX_OTHER_FIELD, "B"), correction(SUM_OF_MIN)])
    accepted, stats = BG.generate_set(chat, 2, "anon_shapes")
    assert [b["macro_blueprint"] for b in accepted] == [ADD_MIN_MAX_FIELD, SUM_OF_MIN]
    assert "accepted blueprint" in chat.prompts[2]
    assert stats.duplicate_rejections == 1 and stats.example_copy_rejections == 0


def test_verify_set_reports_copies_duplicates_and_slot_free_blueprints():
    good = [{"name": "A", "macro_blueprint": ADD_MIN_MAX}, {"name": "B", "macro_blueprint": SUM_OF_MIN}]
    assert BG.verify_set(good, "current") == []
    bad = good + [
        {"name": "C", "macro_blueprint": EXAMPLE_COPY_OTHER_FIELD},
        {"name": "D", "macro_blueprint": ADD_MIN_MAX_FIELD.replace("pv_low", "?")},
        {"name": "E", "macro_blueprint": NO_SLOT},
    ]
    problems = " | ".join(BG.verify_set(bad, "current"))
    assert "C: copies example" in problems and "D: same structure as A" in problems and "E:" in problems


# --- tuning harness ---------------------------------------------------------

def test_tuning_writes_runs_csv_and_accepted_json_with_correct_counts(tmp_path):
    replies = [
        # variant "current": round 1 copies an example, correction fixes it; round 2 duplicates round 1
        reply(EXAMPLE_COPY, "A"), correction(ADD_MIN_MAX),
        reply(ADD_MIN_MAX, "B"), correction(SUM_OF_MIN),
        # variant "anon_rules": round 1 has no slot, correction fixes it; round 2 copies a library illustration
        reply(NO_SLOT, "C"), correction(RATIO_ROOT),
        reply("ts_mean(?)", "D"), correction(MULT_MIN_MAX),
    ]
    chat = FakeChat(replies)
    frame = BG.run_tuning(chat, ["current", "anon_rules"], [{"temperature": 0.5}], 2, str(tmp_path),
                          model="ollama-9b")

    csv = pd.read_csv(tmp_path / "runs.csv")
    assert list(csv.columns) == ["variant", "params", "n_requested", "n_accepted", "compile_rate", "slot_rate",
                                 "example_copy_rejections", "duplicate_rejections", "distinct_structures",
                                 "rounds_used", "seconds"]
    assert len(csv) == 2 and len(frame) == 2
    current, anon = csv.iloc[0], csv.iloc[1]
    assert (current.variant, current.n_requested, current.n_accepted) == ("current", 2, 2)
    assert (current.example_copy_rejections, current.duplicate_rejections) == (1, 1)
    assert (current.compile_rate, current.slot_rate, current.rounds_used) == (1.0, 1.0, 2)
    assert current.distinct_structures == 3          # example skeleton, add(min, max), ts_sum(ts_min)
    assert json.loads(current.params) == {"temperature": 0.5}
    assert (anon.variant, anon.n_accepted) == ("anon_rules", 2)
    assert (anon.example_copy_rejections, anon.duplicate_rejections) == (1, 0)
    assert (anon.compile_rate, anon.slot_rate, anon.rounds_used) == (1.0, 0.5, 2)
    assert anon.distinct_structures == 3             # div, ts_mean, mult

    saved = json.loads((tmp_path / "accepted" / "01_current.json").read_text(encoding="utf-8"))
    assert saved["variant"] == "current" and saved["prompt_sha256"] == prompt_hash("current")
    assert [b["macro_blueprint"] for b in saved["blueprints"]] == [ADD_MIN_MAX, SUM_OF_MIN]
    assert (tmp_path / "accepted" / "02_anon_rules.json").exists()


# --- real-set builder -------------------------------------------------------

def test_build_set_writes_set_and_record_when_criteria_hold(tmp_path):
    chat = FakeChat([reply(ADD_MIN_MAX, "A"), reply(SUM_OF_MIN, "B")])
    assert BG.build_set(chat, 2, "anon_shapes", {"temperature": 0.4}, "ollama-9b", str(tmp_path))
    blueprints = json.loads((tmp_path / "blueprints.json").read_text(encoding="utf-8"))
    record = json.loads((tmp_path / "generation.json").read_text(encoding="utf-8"))
    assert [b["macro_blueprint"] for b in blueprints] == [ADD_MIN_MAX, SUM_OF_MIN]
    assert record["variant"] == "anon_shapes" and record["params"] == {"temperature": 0.4}
    assert record["model"] == "qwen3.5:9b" and record["prompt_sha256"] == prompt_hash("anon_shapes")
    assert record["blueprints_sha256"] == hashlib.sha256((tmp_path / "blueprints.json").read_bytes()).hexdigest()


def test_build_set_writes_nothing_when_the_round_budget_runs_out(tmp_path):
    out = tmp_path / "set"
    chat = FakeChat([reply(SHAPE_COPY, "A"), correction(SHAPE_COPY)] * 3)
    assert not BG.build_set(chat, 2, "anon_shapes", {}, "ollama-9b", str(out), rounds_per_blueprint=1)
    assert not out.exists()


OUTDATED_DIMENSION_LINE = "The others keep the dimension of their input."


@pytest.mark.parametrize("variant", ["anon_rules", "anon_shapes"])
def test_anon_prompts_state_the_dimension_rules_and_not_the_outdated_line(variant):
    prompt = build_idea_prompt("60m", [], 1, 1, variant=variant)
    assert OUTDATED_DIMENSION_LINE not in prompt
    for rule in ("`ts_argmax`, `ts_argmin`, `ts_corr` always return a RATIO",
                 "at least one side MUST be a RATIO", "divisor is a RATIO", "fillable within the depth limit"):
        assert rule in prompt
    for fragment in ("ts_zscore(?)", "ts_rank(?)"):
        assert fragment in variant_examples(variant)


def test_current_prompt_keeps_the_original_dimension_line():
    assert OUTDATED_DIMENSION_LINE in build_idea_prompt("60m", [], 1, 1, variant="current")
