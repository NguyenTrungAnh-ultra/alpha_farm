import hashlib
import json
import re
from itertools import product

import pytest

from strategy_workflows import BlueprintGeneration as BG
from strategy_workflows import GenerateStrategies
from utilities.Prompts import build_batch_prompt, build_feedback_prompt

MARKET_NAME = re.compile(r"vn30|vietnam|viet nam|\bhose\b|hanoi|ho chi minh", re.IGNORECASE)
ROLLING = ("ts_mean", "ts_sum", "ts_max", "ts_min")


def skeletons(n):
    """n distinct valid skeletons (different operators, so different structures), none a prompt example of anon_rules."""
    out = [f"{outer}({a}(?), {b}(?))" for outer in ("sub", "add") for a, b in product(ROLLING, ROLLING)]
    assert n <= len(out)
    return out[:n]


def idea(blueprint, name):
    return {"name": name, "timeframe": "60m", "family": "volatility-regime", "description": "test",
            "macro_blueprint": blueprint}


def batch_reply(blueprints, prefix="Idea"):
    return json.dumps({"ideas": [idea(b, f"{prefix}{i}") for i, b in enumerate(blueprints)]})


def correction_reply(blueprints):
    return json.dumps({"ideas": [{"macro_blueprint": b} for b in blueprints]})


class FakeChat:
    """Stands in for OllamaChatClient: returns queued replies; records prompts and every keyword given to send."""
    model = "fake"
    host = "http://fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts, self.options, self.kwargs = [], [], []

    def send(self, prompt, schema=None, options=None, **extra):
        self.prompts.append(prompt)
        self.options.append(options)
        self.kwargs.append({"schema": schema, **extra})
        reply = self.replies.pop(0) if self.replies else ""
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture(autouse=True)
def no_experience_log(monkeypatch):
    monkeypatch.setattr(GenerateStrategies, "load_experience_log", lambda *a, **k: "")


def test_parse_ideas_accepts_wrapped_bare_and_single_replies_only():
    one = idea("ts_mean(?)", "A")
    assert BG.parse_ideas(json.dumps({"ideas": [one, one]})) == [one, one]
    assert BG.parse_ideas(json.dumps([one])) == [one]
    assert BG.parse_ideas(json.dumps(one)) == [one]
    assert BG.parse_ideas("```json\n" + json.dumps({"ideas": [one]}) + "\n```") == [one]
    assert BG.parse_ideas(json.dumps({"ideas": [one, "junk", 3]})) == [one]
    assert BG.parse_ideas("") is None and BG.parse_ideas("no json here") is None
    assert BG.parse_ideas(json.dumps({"ideas": "text"})) == [{"ideas": "text"}]


def run_batch(replies, n=10, accepted=None, options=None):
    chat = FakeChat(replies)
    asker = BG.LLMAsker(chat, options, model="ollama-9b")
    accepted = [] if accepted is None else accepted
    keys, names, stats = {}, set(), BG.GenerationStats(n_requested=n)
    for bp in accepted:
        keys[BG.blueprint_key(bp["macro_blueprint"])] = bp["macro_blueprint"]
        names.add(bp["name"])
    count = BG.generate_batch(asker, n, "PROMPT", BG.variant_example_keys("anon_rules"), accepted, keys, names, stats)
    return chat, asker, accepted, stats, count


def test_all_valid_batch_is_one_request_with_no_correction():
    chat, asker, accepted, stats, count = run_batch([batch_reply(skeletons(10))])
    assert count == 10 and len(accepted) == 10 and asker.requests == 1
    assert chat.prompts == ["PROMPT"]
    assert (stats.ideas, stats.compiled, stats.with_slot, stats.rounds_used) == (10, 10, 10, 1)
    assert stats.example_copy_rejections == stats.duplicate_rejections == 0


def test_rejected_ideas_go_into_one_correction_request_and_are_accepted_when_fixed():
    good = skeletons(12)
    no_slot = "sub(ts_mean(pv_close), ts_max(pv_close))"
    example_copy = "ts_mean(?)"                              # a library illustration of anon_rules
    unknown = "sub(ema(?), ts_max(?))"
    first = good[:7] + [no_slot, example_copy, unknown]
    chat, asker, accepted, stats, count = run_batch([batch_reply(first), correction_reply(good[7:10])])
    assert count == 10 and [b["macro_blueprint"] for b in accepted] == good[:10]
    assert asker.requests == 2 and len(chat.prompts) == 2
    correction_prompt = chat.prompts[1]
    for bad in (no_slot, example_copy, unknown):
        assert bad in correction_prompt
    assert "no `?` slot" in correction_prompt and "example skeleton" in correction_prompt
    assert (stats.ideas, stats.compiled, stats.with_slot) == (10, 9, 8)      # `ema` does not compile, `no_slot` has no `?`
    assert stats.example_copy_rejections == 1 and stats.rounds_used == 2


def test_duplicate_structure_inside_one_reply_is_rejected_then_corrected():
    good = skeletons(4)
    twin = good[0]                                   # same structure again
    _, _, accepted, stats, count = run_batch([batch_reply(good[:3] + [twin]), correction_reply([good[3]])], n=4)
    assert count == 4 and [b["macro_blueprint"] for b in accepted] == good
    assert stats.duplicate_rejections == 1


def test_a_still_invalid_correction_is_not_retried():
    good = skeletons(3)
    chat, asker, accepted, stats, count = run_batch(
        [batch_reply(good[:2] + ["no_such_op(?)"]), correction_reply(["still_bad(?)"]), "SHOULD NOT BE ASKED"], n=3)
    assert count == 2 and asker.requests == 2 and chat.replies == ["SHOULD NOT BE ASKED"]


def test_no_correction_request_when_the_batch_is_already_full():
    good = skeletons(4)
    chat, asker, accepted, _, count = run_batch([batch_reply(good[:3] + ["no_such_op(?)"])], n=3)
    assert count == 3 and asker.requests == 1


def test_extra_ideas_beyond_n_are_ignored():
    _, _, accepted, stats, count = run_batch([batch_reply(skeletons(6))], n=4)
    assert count == 4 and stats.ideas == 6


def test_chat_failure_returns_nothing_and_does_not_raise():
    _, asker, accepted, stats, count = run_batch([RuntimeError("ollama down")])
    assert count == 0 and accepted == [] and asker.requests == 1


def test_identical_names_get_a_suffix_instead_of_losing_the_idea():
    ideas = [idea(b, "StrategyName") for b in skeletons(3)]
    _, _, accepted, _, count = run_batch([json.dumps({"ideas": ideas})], n=3)
    assert [b["name"] for b in accepted] == ["StrategyName", "StrategyName_2", "StrategyName_3"]


def test_seed_advances_per_request_and_think_is_never_passed():
    good = skeletons(5)
    chat, asker, *_ = run_batch([batch_reply(good[:3] + ["bad_op(?)", "worse(?)"]), correction_reply(good[3:5])],
                                n=5, options={"seed": 100, "temperature": None})
    assert chat.options == [{"seed": 100, "num_predict": 16384}, {"seed": 101, "num_predict": 16384}]
    assert all(set(kw) <= {"schema"} for kw in chat.kwargs)          # no `think`, no other keyword
    assert [kw["schema"] for kw in chat.kwargs] == [None, None]      # ollama-9b: no JSON schema forced
    fixed = FakeChat([batch_reply(skeletons(2))])
    BG.generate_batch(BG.LLMAsker(fixed, None, "ollama-local"), 2, "P", BG.variant_example_keys("anon_rules"),
                      [], {}, set(), BG.GenerationStats())
    assert fixed.options == [{"num_predict": 16384}] and fixed.kwargs[0]["schema"] == "json"


def test_initial_set_is_two_requests_of_ten_and_the_second_lists_the_first_ten():
    both = skeletons(20)
    chat = FakeChat([batch_reply(both[:10], "First"), batch_reply(both[10:], "Second")])
    accepted, stats = BG.generate_initial_set(chat, 20, 10, "anon_rules", {"seed": 7}, "ollama-9b")
    assert [b["macro_blueprint"] for b in accepted] == both
    assert len({b["name"] for b in accepted}) == 20
    assert stats.requests == 2 and stats.n_accepted == 20 and stats.llm_seconds >= 0.0
    assert chat.options == [{"seed": 7, "num_predict": 16384}, {"seed": 8, "num_predict": 16384}]
    assert "Design 10 DIFFERENT" in chat.prompts[0] and "ALREADY TAKEN" not in chat.prompts[0]
    assert "ALREADY TAKEN" in chat.prompts[1] and all(bp in chat.prompts[1] for bp in both[:10])
    assert not MARKET_NAME.search(chat.prompts[0]) and not MARKET_NAME.search(chat.prompts[1])


def test_initial_set_repeats_of_the_first_batch_are_rejected_and_corrected():
    both = skeletons(20)
    chat = FakeChat([batch_reply(both[:10]), batch_reply(both[:2] + both[12:]), correction_reply(both[10:12])])
    accepted, stats = BG.generate_initial_set(chat, 20, 10, "anon_rules", None, "ollama-9b")
    assert len(accepted) == 20 and stats.requests == 3 and stats.duplicate_rejections == 2
    assert BG.verify_set(accepted, "anon_rules") == []


def test_initial_set_short_of_the_target_is_returned_as_is():
    chat = FakeChat([batch_reply(skeletons(10)), batch_reply(skeletons(10)[:3] + ["x_(?)"]), "garbage"])
    accepted, stats = BG.generate_initial_set(chat, 20, 10, "anon_rules", None, "ollama-9b")
    assert len(accepted) == 10 and stats.n_accepted == 10


def test_build_set_with_batches_writes_the_set_and_the_batch_size(tmp_path):
    both = skeletons(20)
    chat = FakeChat([batch_reply(both[:10]), batch_reply(both[10:])])
    assert BG.build_set(chat, 20, "anon_rules", {"seed": 1}, "ollama-9b", str(tmp_path), batch_size=10)
    record = json.loads((tmp_path / "generation.json").read_text(encoding="utf-8"))
    blueprints = json.loads((tmp_path / "blueprints.json").read_text(encoding="utf-8"))
    assert len(blueprints) == 20 and record["batch_size"] == 10
    assert record["stats"]["requests"] == 2
    assert record["blueprints_sha256"] == hashlib.sha256((tmp_path / "blueprints.json").read_bytes()).hexdigest()


def test_build_set_with_batches_writes_nothing_when_short(tmp_path):
    chat = FakeChat([batch_reply(skeletons(10)), batch_reply(["bad(?)"] * 10), correction_reply(["bad(?)"] * 10)])
    out = tmp_path / "set"
    assert not BG.build_set(chat, 20, "anon_rules", {}, "ollama-9b", str(out), batch_size=10)
    assert not out.exists()


# --- feedback round ---------------------------------------------------------

SCORED = [
    {"expression": "sub(pv_close, ts_mean(pv_close, 10))", "reward": 0.4123, "rank_ic": 0.031},
    {"expression": "ts_zscore(pv_volume, 5)", "reward": 0.2, "rank_ic": -0.02},
]


def test_feedback_blueprints_must_differ_from_the_initial_set_and_from_each_other():
    pool = skeletons(14)
    initial = [{"name": f"Init{i}", "macro_blueprint": b} for i, b in enumerate(pool[:4])]
    reply = batch_reply(pool[:2] + pool[4:8])              # first two repeat initial blueprints
    chat = FakeChat([reply, correction_reply([pool[8], pool[9]])])
    new, stats, prompt = BG.generate_feedback_blueprints(chat, 6, SCORED, initial, "anon_rules", {"seed": 5},
                                                         "ollama-9b")
    assert [b["macro_blueprint"] for b in new] == pool[4:10]
    assert stats.requests == 2 and stats.duplicate_rejections == 2 and stats.n_accepted == 6
    assert prompt == chat.prompts[0]
    assert all(b["macro_blueprint"] in prompt for b in initial)           # listed as taken
    assert chat.options == [{"seed": 5, "num_predict": 16384}, {"seed": 6, "num_predict": 16384}]
    assert not ({b["name"] for b in new} & {b["name"] for b in initial})


def test_feedback_name_clash_with_an_initial_blueprint_is_suffixed():
    initial = [{"name": "Idea0", "macro_blueprint": skeletons(1)[0]}]
    chat = FakeChat([batch_reply(skeletons(3)[1:2])])
    new, _, _ = BG.generate_feedback_blueprints(chat, 1, SCORED, initial, "anon_rules", None, "ollama-9b")
    assert new[0]["name"] == "Idea0_2"


# --- prompts ----------------------------------------------------------------

def test_feedback_prompt_shows_train_numbers_only_and_hides_the_market():
    prompt = build_feedback_prompt("60m", 10, SCORED, ["sub(ts_mean(?), ts_max(?))"], "anon_rules")
    assert not MARKET_NAME.search(prompt)
    assert "index futures contract" in prompt
    for item in SCORED:
        assert item["expression"] in prompt
    assert "reward 0.4123, rank IC +0.0310" in prompt and "reward 0.2000, rank IC -0.0200" in prompt
    numbers = re.findall(r"reward (-?\d+\.\d+), rank IC ([+-]\d+\.\d+)", prompt)
    assert len(numbers) == len(SCORED)                       # no other reward / IC figure appears
    lowered = prompt.lower()
    for word in ("validation", "evaluation", "out-of-sample", "sharpe", "calmar"):
        assert word not in lowered
    assert "Design 10 NEW skeletons" in prompt and '"ideas"' in prompt


def test_batch_prompt_asks_for_the_ideas_object_and_lists_what_to_avoid():
    prompt = build_batch_prompt("60m", 10, ["sub(ts_mean(?), ts_max(?))"], "anon_rules")
    assert '"ideas"' in prompt and "list of 10 objects" in prompt
    assert "sub(ts_mean(?), ts_max(?))" in prompt and "ALREADY TAKEN" in prompt
    assert "ALREADY TAKEN" not in build_batch_prompt("60m", 10, [], "anon_rules")
    assert not MARKET_NAME.search(prompt)


# --- attaching to a running model ---------------------------------------------

def test_attach_builds_a_client_without_starting_or_creating_anything(monkeypatch):
    from llm_clients import OllamaClient
    from llm_clients.OllamaClient import OllamaChatClient

    def forbidden(*args, **kwargs):
        raise AssertionError("attach must not touch the network or start processes")

    monkeypatch.setattr(OllamaClient.requests, "get", forbidden)
    monkeypatch.setattr(OllamaClient.subprocess, "Popen", forbidden)
    monkeypatch.setattr(OllamaClient.subprocess, "run", forbidden)
    seen = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "{}"}

    monkeypatch.setattr(OllamaClient.requests, "post",
                        lambda url, json=None, timeout=None: seen.update(url=url, payload=json) or Response())
    client = OllamaChatClient.attach("alpha_farm_custom", "http://h:1")
    assert (client.model, client.host, client.server_process) == ("alpha_farm_custom", "http://h:1", None)
    client.send("hi", schema="json", options={"seed": 5})
    assert seen["url"] == "http://h:1/api/generate" and seen["payload"]["model"] == "alpha_farm_custom"
    assert seen["payload"]["options"]["seed"] == 5 and "think" not in seen["payload"]


# --- decided configuration: anon_shapes, top-up, timeout -----------------------

def test_batched_defaults_use_anon_shapes_and_its_examples():
    from strategy_workflows import SearchConfigs
    from utilities.Prompts import SHAPE_EXAMPLES
    assert SearchConfigs.FEEDBACK_VARIANT == "anon_shapes"
    for prompt in (build_batch_prompt("60m", 10, []), build_feedback_prompt("60m", 10, SCORED)):
        assert "SHAPES (GRAMMAR ILLUSTRATION ONLY)" in prompt and SHAPE_EXAMPLES[0] in prompt
        assert not MARKET_NAME.search(prompt)
    chat = FakeChat([batch_reply([SHAPE_EXAMPLES[0]] + skeletons(1)), correction_reply(skeletons(2)[1:])])
    accepted, stats = BG.generate_initial_set(chat, 2, 2)           # variant not given
    assert stats.example_copy_rejections == 1 and len(accepted) == 2
    assert "Shape 1" in chat.prompts[0]
    chat = FakeChat([batch_reply(skeletons(1))])
    new, _, prompt = BG.generate_feedback_blueprints(chat, 1, SCORED, [{"name": "I", "macro_blueprint": "ts_max(?)"}])
    assert "Shape 1" in prompt and len(new) == 1


def test_initial_set_tops_up_until_twenty_with_each_request_listing_the_accepted():
    both = skeletons(32)
    chat = FakeChat([batch_reply(both[:6]), batch_reply(both[6:14]), batch_reply(both[14:24])])
    accepted, stats = BG.generate_initial_set(chat, 20, 10, "anon_shapes", None, "ollama-9b")
    assert [b["macro_blueprint"] for b in accepted] == both[:20]
    assert len(chat.prompts) == 3 == stats.requests
    assert "Design 10 DIFFERENT" in chat.prompts[0] and "Design 10 DIFFERENT" in chat.prompts[1]
    assert "Design 6 DIFFERENT" in chat.prompts[2]                    # only 20 - 14 still needed
    assert all(bp in chat.prompts[2] for bp in both[:14])


def test_top_up_stops_at_five_batched_requests_plus_their_corrections(tmp_path):
    good = skeletons(4)
    # every request returns one valid and one invalid idea; every correction fails
    replies = []
    for i in range(7):
        replies += [batch_reply([good[i % 4] if i < 4 else "bad(?)", "bad2(?)"]), correction_reply(["bad(?)"])]
    chat = FakeChat(replies)
    accepted, stats = BG.generate_initial_set(chat, 20, 10, "anon_shapes", None, "ollama-9b")
    assert len(accepted) == 4 and stats.requests == 10               # 5 batched + 5 corrections, no more
    assert len(chat.replies) == 4
    out = tmp_path / "set"
    assert not BG.build_set(FakeChat(list(replies)), 20, "anon_shapes", {}, "ollama-9b", str(out), batch_size=10)
    assert not out.exists()


def test_request_timeout_is_a_client_parameter_and_batches_wait_hours_behind_the_queue(monkeypatch):
    from llm_clients import OllamaClient
    from llm_clients.OllamaClient import OllamaChatClient
    from strategy_workflows import SearchConfigs
    seen = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "{}"}

    monkeypatch.setattr(OllamaClient.requests, "post", lambda url, json=None, timeout=None: seen.append(timeout) or Response())
    OllamaChatClient.attach("m").send("x")
    OllamaChatClient.attach("m", request_timeout=42).send("x")
    legacy = OllamaChatClient.__new__(OllamaChatClient)
    legacy.model, legacy.host, legacy.verbose = "m", "http://x", False
    legacy.send("x")
    SearchConfigs.create_worker_chat({"name": "m", "host": "http://x"}).send("x")
    assert seen == [(10, 300), (10, 42), (10, 300), (10, 6 * 3600)]       # (connect, read)
    chat = FakeChat([])
    BG.LLMAsker(chat)
    assert chat.request_timeout == 6 * 3600 and chat.strict_reply is True
