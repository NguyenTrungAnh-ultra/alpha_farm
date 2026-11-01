"""Failure handling of the LLM feedback round: strict replies, recorded reasons, window-free prompt, summary."""

import json

import pandas as pd
import pytest
import requests

from llm_clients import OllamaClient
from llm_clients.OllamaClient import NUM_CTX, OllamaChatClient, OllamaReplyError
from strategy_workflows import BlueprintGeneration as BG
from strategy_workflows import RunRQ1 as rq
from strategy_workflows import SearchConfigs as sc
from strategy_workflows import WalkForward as wf
from strategy_workflows.RunPlantedSignal import quiet
from tests.test_batched_blueprints import FakeChat, batch_reply, correction_reply, skeletons
from utilities.Prompts import build_feedback_prompt

SCORED = [{"expression": "sub(pv_close, ts_mean(pv_close))", "reward": 0.4, "rank_ic": 0.03}]


class Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def send_reply(monkeypatch, data, strict):
    monkeypatch.setattr(OllamaClient.requests, "post", lambda url, json=None, timeout=None: Response(data))
    client = OllamaChatClient.attach("m", "http://x")
    if strict:
        client.strict_reply = True
    return client.send("hi")


# --- the client -------------------------------------------------------------

def test_context_is_32k_and_strict_client_refuses_a_cut_off_reply(monkeypatch):
    assert NUM_CTX == 32768
    cut = {"response": "", "thinking": "step 1 ... step 2", "done_reason": "length",
           "prompt_eval_count": 2506, "eval_count": 13878}
    with pytest.raises(OllamaReplyError) as raised:
        send_reply(monkeypatch, cut, strict=True)
    assert raised.value.kind == "context_length" and "2506" in str(raised.value)
    with pytest.raises(OllamaReplyError) as raised:                     # truncated JSON is no answer either
        send_reply(monkeypatch, {"response": '{"ideas": [', "done_reason": "length"}, strict=True)
    assert raised.value.kind == "context_length"
    with pytest.raises(OllamaReplyError) as raised:
        send_reply(monkeypatch, {"response": " ", "thinking": "t", "done_reason": "stop"}, strict=True)
    assert raised.value.kind == "empty_reply"
    assert send_reply(monkeypatch, {"response": "ok", "done_reason": "stop"}, strict=True) == "ok"


def test_other_callers_keep_the_thinking_fallback(monkeypatch):
    cut = {"response": "", "thinking": "only thoughts", "done_reason": "length"}
    assert send_reply(monkeypatch, cut, strict=False) == "only thoughts"


def test_the_asker_makes_the_client_strict_and_a_cut_off_reply_is_recorded_as_the_failure():
    class Cut(FakeChat):
        def send(self, prompt, schema=None, options=None, **extra):
            raise OllamaReplyError("context_length", "cut off")

    chat = Cut([])
    new, stats, _ = BG.generate_feedback_blueprints(chat, 3, SCORED, [], "anon_shapes", None, "ollama-9b")
    assert chat.strict_reply is True and new == []
    assert stats.error == "context_length" and stats.requests == 3 and stats.retries == 2


# --- recorded reasons ---------------------------------------------------------

@pytest.mark.parametrize("failure, label", [
    (requests.exceptions.ReadTimeout("slow"), "timeout"),
    (requests.exceptions.ConnectionError("down"), "connection"),
    (RuntimeError("boom"), "exception: RuntimeError: boom"),
    ("no json here", "no_json"),
    (json.dumps({"ideas": []}), "no_ideas"),
])
def test_first_request_failure_is_labelled(failure, label):
    stats = BG.GenerationStats(n_requested=3)
    BG.generate_batch(BG.LLMAsker(FakeChat([failure]), None, "ollama-9b"), 3, "P", {}, [], {}, set(), stats)
    assert stats.error == label


def test_rejections_are_counted_by_kind_before_and_after_the_correction():
    good = skeletons(4)
    windowed = "mult(ts_argmax(pv_close, ?), ts_sum(pv_volume, ?))"          # the copied two-argument form
    first = good[:1] + [windowed, "ema(?)", "sub(ts_mean(pv_close), ts_max(pv_close))", good[0]]
    fixed = [good[1], good[2], windowed, good[3]]
    chat = FakeChat([batch_reply(first), correction_reply(fixed)])
    stats = BG.GenerationStats(n_requested=5)
    accepted = []
    BG.generate_batch(BG.LLMAsker(chat, None, "ollama-9b"), 5, "P", {}, accepted, {}, set(), stats)
    assert stats.rejections == {"arity": 1, "unknown_operator": 1, "no_slot": 1, "duplicate": 1}
    assert stats.rejections_after_correction == {"arity": 1}
    assert stats.error == stats.correction_error == "" and len(accepted) == 4


def test_failed_correction_request_is_recorded():
    chat = FakeChat([batch_reply(["ema(?)"]), requests.exceptions.ReadTimeout("slow")])
    stats = BG.GenerationStats()
    BG.generate_batch(BG.LLMAsker(chat, None, "ollama-9b"), 1, "P", {}, [], {}, set(), stats)
    assert stats.correction_error == "timeout" and stats.error == ""


def test_schema_rejection_kind():
    stats = BG.GenerationStats()
    bad = json.dumps({"ideas": [{"name": "x", "macro_blueprint": "sub(ts_mean(?), ts_max(?))"}]})
    BG.generate_batch(BG.LLMAsker(FakeChat([bad, "garbage"]), None, "ollama-9b"), 1, "P", {}, [], {}, set(), stats)
    assert stats.rejections == {"schema": 1} and stats.correction_error == "no_json"


def feedback_round(chat, items=None):
    engine = type("E", (), {})()
    outcome = sc.SearchOutcome(system="llm_mcts")
    plan = sc.BudgetPlan(feedback_blueprints=3)
    original = sc.feedback_items
    sc.feedback_items = lambda *_: SCORED if items is None else items
    try:
        sc._feedback_round(engine, plan, [], "k", chat, outcome, "ollama-9b")
    finally:
        sc.feedback_items = original
    return outcome.feedback


def test_feedback_info_keeps_the_old_fields_and_adds_the_reason():
    info = feedback_round(FakeChat([RuntimeError("x")]))
    assert {"n_scored", "prompt_sha256", "n_new", "fallback", "requests", "llm_s", "seed", "ideas", "compiled",
            "with_slot", "example_copy_rejections", "duplicate_rejections"} <= set(info)
    assert info["fallback"] is True and info["error"].startswith("exception: RuntimeError")
    assert info["correction_error"] == "" and info["rejections"] == {}
    json.dumps(info)                                                             # goes into runs.csv as JSON


def test_feedback_info_reasons_for_rejection_success_and_nothing_to_ask():
    info = feedback_round(FakeChat([batch_reply(["ema(?)"]), correction_reply(["ema(?)"])]))
    assert info["error"] == "all_rejected" and info["fallback"] is True
    assert info["rejections"] == {"unknown_operator": 1} and info["rejections_after_correction"] == {"unknown_operator": 1}
    ok = feedback_round(FakeChat([batch_reply(skeletons(2))]))
    assert ok["error"] == "" and ok["fallback"] is False and ok["n_new"] == 2
    none = feedback_round(FakeChat([]), items=[])
    assert none["error"] == "no_scored_formulas" and none["fallback"] is True and none["requests"] == 0


# --- the prompt ---------------------------------------------------------------

def test_feedback_items_show_no_window_and_merge_formulas_that_differ_only_in_windows():
    candidates = [
        {"expr": "(close - ts_mean(close, 10))", "reward": 0.5, "metrics": {"rank_ic": 0.02}},
        {"expr": "(close - ts_mean(close, 20))", "reward": 0.4, "metrics": {"rank_ic": 0.03}},
        {"expr": "ts_corr(close, volume, 5)", "reward": 0.3, "metrics": {}},
    ]
    engine = type("E", (), {"get_best_candidates": lambda self: candidates})()
    items = sc.feedback_items(engine, 5)
    assert [i["expression"] for i in items] == ["sub(pv_close, ts_mean(pv_close))", "ts_corr(pv_close, pv_volume)"]
    assert items[0]["reward"] == 0.5 and items[0]["rank_ic"] == 0.02            # the better of the two windows
    prompt = build_feedback_prompt("60m", 10, items, [], "anon_shapes")
    section = prompt[prompt.index("## FEEDBACK"):prompt.index("## CURRENT MISSION")]
    assert "ts_mean(pv_close)" in section and "ts_corr(pv_close, pv_volume)" in section
    assert "reward 0.5000, rank IC +0.0200" in section
    assert not any(f", {w})" in section for w in (5, 10, 20))
    assert len(sc.feedback_items(engine, 1)) == 1


def test_correction_prompt_names_no_window_value():
    from utilities.Prompts import build_batch_correction_prompt
    text = build_batch_correction_prompt([("sub(ts_mean(?), ts_max(?))", "no `?` slot")])
    assert "a window is never an argument" in text


# --- worker output ------------------------------------------------------------

def test_generation_messages_reach_stderr_even_when_stdout_is_silenced(capsys):
    with quiet():
        BG.log("[blueprints] rejected (x)")
        print("engine progress")
    out = capsys.readouterr()
    assert "[blueprints] rejected (x)" in out.err and "engine progress" not in out.out


# --- summary ------------------------------------------------------------------

RECORDS = [
    {"fallback": True, "error": "timeout", "rejections": {}, "rejections_after_correction": {}},
    {"fallback": True, "error": "context_length"},
    {"fallback": True, "error": ""},                                    # run recorded before the reason existed
    {"fallback": False, "error": "", "rejections": {"arity": 4}, "rejections_after_correction": {"arity": 1}},
    {"fallback": False, "rejections": {"arity": 2, "no_slot": 1}},
    {},                                                                  # a run of another system
]


def test_feedback_summary_counts_fallbacks_and_reasons():
    summary = sc.summarize_feedback(RECORDS)
    assert (summary["runs"], summary["fallbacks"]) == (5, 3)
    assert summary["reasons"] == {"timeout": 1, "context_length": 1, "unrecorded": 1}
    assert summary["rejections"] == {"arity": 6, "no_slot": 1} and summary["rejections_after_correction"] == {"arity": 1}
    lines = sc.feedback_summary_lines(summary, "[x]")
    assert "5 runs, 3 fell back" in lines[0] and "(60%)" in lines[0]
    assert "timeout 1" in lines[1] and "arity 6, no_slot 1" in lines[2]
    assert sc.feedback_summary_lines(sc.summarize_feedback([{}]), "[x]") == []


def test_feedback_records_drop_a_rerun_and_unreadable_cells():
    runs = pd.DataFrame({"seed": [1, 1, 2, 3], "feedback": [json.dumps({"fallback": True}),
                                                           json.dumps({"fallback": False}), "{}", None]})
    assert sc.feedback_records(runs, ["seed"]) == [{"fallback": False}, {}]
    assert sc.feedback_records(pd.DataFrame({"seed": [1]}), ["seed"]) == []


def write_runs(path, key_columns, feedbacks):
    rows = [{**{k: v for k, v in zip(key_columns, values)}, "feedback": json.dumps(fb)}
            for values, fb in feedbacks]
    pd.DataFrame(rows).to_csv(path, index=False)


def test_walkforward_summary_prints_the_feedback_fallback_count(tmp_path, capsys, monkeypatch):
    out_dir = tmp_path / "llm_mcts"
    out_dir.mkdir()
    pd.DataFrame({"date": ["2024-01-01"], "window": [1], "seed": [1], "mode": ["placebo"], "placebo_set": [1],
                  "return": [0.01]}).to_csv(out_dir / "returns.csv", index=False)
    write_runs(out_dir / "runs.csv", wf.RUN_KEY, [
        (("placebo", 1, 1, 1), {"fallback": True, "error": "context_length"}),
        (("placebo", 1, 2, 1), {"fallback": False, "error": ""}),
    ])
    monkeypatch.setattr(wf, "step_compare", lambda args: None)
    args = type("A", (), {"results_root": str(tmp_path), "config": None, "system": "llm_mcts"})()
    wf.step_summary(args)
    printed = capsys.readouterr().out
    assert "[walkforward] feedback round: 2 runs, 1 fell back" in printed and "context_length 1" in printed


def test_rq1_summary_prints_the_feedback_fallback_count(tmp_path, capsys, monkeypatch):
    base = dict(config="llm_mcts", ic=0.1, run_formula="A1", seed=1, a="A1", budget=50, near=True, touched=False,
                best_corr_top5=0.4, closest_corr=0.5, touch_iterations=float("nan"), touch_wall_s=float("nan"))
    pd.DataFrame([base]).to_csv(tmp_path / "checkpoints.csv", index=False)
    write_runs(tmp_path / "runs.csv", rq.RUN_KEY, [
        (("llm_mcts", 0.1, "A1", 1), {"fallback": True, "error": "timeout"}),
        (("mcts_only", 0.1, "A1", 1), {}),
    ])
    for name in ("summarize_checkpoints", "primary_tests", "detection_thresholds", "first_touch_table"):
        monkeypatch.setattr(rq, name, lambda checkpoints: pd.DataFrame({"x": [1]}))
    rq.step_summary(type("A", (), {"out_dir": str(tmp_path)})())
    printed = capsys.readouterr().out
    assert "[rq1] feedback round: 1 runs, 1 fell back" in printed and "timeout 1" in printed
