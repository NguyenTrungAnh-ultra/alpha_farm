"""Token cap and retry of cut-off replies in `LLMAsker`, and how retries are recorded."""

import requests

from llm_clients import OllamaClient
from llm_clients.OllamaClient import OllamaChatClient, OllamaReplyError
from strategy_workflows import BlueprintGeneration as BG
from strategy_workflows import SearchConfigs as sc
from tests.test_batched_blueprints import FakeChat, batch_reply, skeletons
from tests.test_feedback_failures import Response, feedback_round

CUT = OllamaReplyError("context_length", "cut off")
EMPTY = OllamaReplyError("empty_reply", "empty")


def test_client_passes_num_predict_through(monkeypatch):
    seen = {}
    monkeypatch.setattr(OllamaClient.requests, "post",
                        lambda url, json=None, timeout=None: seen.update(json) or Response({"response": "ok"}))
    OllamaChatClient.attach("m", "http://x").send("hi", options={"num_predict": 5})
    assert seen["options"]["num_predict"] == 5


def test_every_request_carries_the_token_cap_and_attempts_get_distinct_deterministic_seeds():
    def run():
        chat = FakeChat([CUT, EMPTY, "ok"])
        asker = BG.LLMAsker(chat, {"seed": 100}, "ollama-9b")
        assert asker.ask("P") == "ok"
        return chat, asker

    chat, asker = run()
    assert [o["num_predict"] for o in chat.options] == [BG.MAX_GENERATED_TOKENS] * 3 == [16384] * 3
    assert [o["seed"] for o in chat.options] == [100, 101, 102]
    assert asker.requests == 3 and asker.retry_errors == ["context_length", "empty_reply"]
    assert [o["seed"] for o in run()[0].options] == [100, 101, 102]
    assert FakeChat([]).options == []
    nxt = FakeChat(["a"])
    asker.chat = nxt
    asker.ask("Q")
    assert nxt.options[0]["seed"] == 103                          # the sequence continues across asks


def test_gives_up_after_three_attempts_and_raises_the_last_error():
    chat = FakeChat([CUT, CUT, EMPTY, "never"])
    asker = BG.LLMAsker(chat, None, "ollama-9b")
    try:
        asker.ask("P")
        raise AssertionError("expected OllamaReplyError")
    except OllamaReplyError as exc:
        assert exc.kind == "empty_reply"
    assert len(chat.prompts) == 3 and asker.requests == 3 and chat.replies == ["never"]


def test_timeout_connection_and_other_errors_are_not_retried():
    for failure in (requests.exceptions.ReadTimeout("slow"), requests.exceptions.ConnectionError("x"), RuntimeError("b")):
        chat = FakeChat([failure, "ok"])
        asker = BG.LLMAsker(chat, None, "ollama-9b")
        try:
            asker.ask("P")
            raise AssertionError("expected an error")
        except type(failure):
            pass
        assert len(chat.prompts) == 1 and asker.retry_errors == []


def test_retries_are_recorded_in_stats_and_feedback_info():
    info = feedback_round(FakeChat([CUT, CUT, batch_reply(skeletons(2))]))
    assert info["retries"] == 2 and info["retry_errors"] == ["context_length", "context_length"]
    assert info["requests"] == 3 and info["error"] == "" and info["fallback"] is False


def test_all_attempts_failing_keeps_the_error_kind():
    info = feedback_round(FakeChat([CUT, CUT, CUT]))
    assert info["error"] == "context_length" and info["fallback"] is True
    assert info["retries"] == 2 and info["requests"] == 3
    clean = feedback_round(FakeChat([batch_reply(skeletons(1))]))
    assert clean["retries"] == 0 and clean["retry_errors"] == []


def test_correction_request_retries_too():
    chat = FakeChat([batch_reply(["ema(?)"]), EMPTY, BG.parse_ideas and '{"ideas": []}'])
    stats = BG.GenerationStats()
    BG.generate_batch(BG.LLMAsker(chat, None, "ollama-9b"), 1, "P", {}, [], {}, set(), stats)
    assert len(chat.prompts) == 3 and stats.correction_error == "no_ideas"


def test_summary_counts_runs_with_retry_and_cut_off_attempts():
    records = [
        {"fallback": False, "error": "", "retries": 2, "retry_errors": ["context_length", "empty_reply"]},
        {"fallback": True, "error": "context_length", "retries": 2, "retry_errors": ["context_length"] * 2},
        {"fallback": False, "error": "", "retries": 0, "retry_errors": []},
        {"fallback": True, "error": "timeout"},
    ]
    summary = sc.summarize_feedback(records)
    assert summary["runs_with_retry"] == 2 and summary["cut_off_attempts"] == 5
    text = "\n".join(sc.feedback_summary_lines(summary, "[x]"))
    assert "runs that needed a retry: 2" in text and "cut off or empty in total: 5" in text
