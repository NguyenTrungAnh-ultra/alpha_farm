import json

import pytest

from strategy_workflows import GenerateStrategies, RunPlantedSignal
from strategy_workflows.GenerateStrategies import validate_idea
from strategy_workflows.SemanticCompiler import SemanticCompiler, SemanticCompilerError, count_slots
from utilities.Prompts import (
    FEW_SHOT_EXAMPLES, SLOT_RIGHT_EXAMPLE, SLOT_WRONG_EXAMPLE, build_correction_prompt, build_idea_prompt,
)

NO_SLOT = "sub(ts_mean(pv_high), ts_mean(pv_low))"
ONE_SLOT = "sub(pv_close, ts_mean(?))"
TWO_SLOTS = "sub(ts_mean(?), ts_mean(?))"
NOT_AN_EXAMPLE = "add(ts_min(?), ts_max(?))"


def idea(blueprint, name="Idea"):
    return {"name": name, "timeframe": "60m", "family": "volatility-regime",
            "description": "test", "macro_blueprint": blueprint}


class FakeChat:
    """Stands in for OllamaChatClient: returns queued replies, records prompts."""
    model = "fake"

    def __init__(self, *args, replies=None, **kwargs):
        self.replies = list(replies if replies is not None else FakeChat.queue)
        self.prompts = []

    def send(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.replies.pop(0) if self.replies else ""

    def stop_keepalive(self):
        pass


def reply(blueprint, name="Idea"):
    return json.dumps(idea(blueprint, name))


# --- slot counting ----------------------------------------------------------

@pytest.mark.parametrize("blueprint, expected", [(NO_SLOT, 0), (ONE_SLOT, 1), (TWO_SLOTS, 2)])
def test_count_slots_on_compiled_blueprints(blueprint, expected):
    assert count_slots(SemanticCompiler().compile_blueprint(blueprint)) == expected


def test_compile_open_blueprint_rejects_slot_free():
    compiler = SemanticCompiler()
    with pytest.raises(SemanticCompilerError, match="no `\\?` slot"):
        compiler.compile_open_blueprint(NO_SLOT)
    assert count_slots(compiler.compile_open_blueprint(ONE_SLOT)) == 1


# --- prompt ----------------------------------------------------------------

def test_every_few_shot_example_compiles_and_has_a_slot():
    compiler = SemanticCompiler()
    prompt = build_idea_prompt("60m", [], 1, 1)
    assert FEW_SHOT_EXAMPLES
    for _, blueprint in FEW_SHOT_EXAMPLES:
        assert count_slots(compiler.compile_open_blueprint(blueprint)) >= 1
        assert blueprint in prompt


def test_prompt_slot_examples_are_right_and_wrong():
    compiler = SemanticCompiler()
    assert count_slots(compiler.compile_blueprint(SLOT_WRONG_EXAMPLE)) == 0
    assert count_slots(compiler.compile_blueprint(SLOT_RIGHT_EXAMPLE)) == 2
    prompt = build_idea_prompt("60m", [], 1, 1)
    assert SLOT_WRONG_EXAMPLE in prompt and "MUST contain at least one `?`" in prompt


# --- GenerateStrategies validation -----------------------------------------

def test_validate_idea_rejects_slot_free_blueprint():
    with pytest.raises(ValueError, match="Macro-Blueprint Semantic Error.*no `\\?` slot"):
        validate_idea(idea(NO_SLOT))
    valid, root = validate_idea(idea(TWO_SLOTS))
    assert valid["macro_blueprint"] == TWO_SLOTS and count_slots(root) == 2


def run_generate(monkeypatch, tmp_path, replies):
    chat = FakeChat(replies=replies)
    monkeypatch.setattr(GenerateStrategies, "OllamaChatClient", lambda *a, **k: chat)
    monkeypatch.setattr(GenerateStrategies, "PROJECT_ROOT", str(tmp_path))
    GenerateStrategies.run_pipeline(n_strategies=1, model="ollama-local", results_dir=str(tmp_path / "ideas"))
    return chat, list((tmp_path / "results" / "ideas").glob("*.json"))


def test_generate_feeds_slot_error_back_and_accepts_the_correction(monkeypatch, tmp_path):
    chat, saved = run_generate(monkeypatch, tmp_path, [reply(NO_SLOT), json.dumps({"macro_blueprint": TWO_SLOTS})])
    assert len(chat.prompts) == 2 and "no `?` slot" in chat.prompts[1]
    assert len(saved) == 1 and json.loads(saved[0].read_text(encoding="utf-8"))["macro_blueprint"] == TWO_SLOTS


def test_generate_discards_blueprint_that_stays_slot_free(monkeypatch, tmp_path):
    _, saved = run_generate(monkeypatch, tmp_path, [reply(NO_SLOT), json.dumps({"macro_blueprint": NO_SLOT})])
    assert saved == []


# --- planted blueprints step -------------------------------------------------

def run_planted(monkeypatch, replies, n=1):
    chat = FakeChat(replies=replies)
    monkeypatch.setattr("llm_clients.OllamaClient.OllamaChatClient", lambda *a, **k: chat)
    monkeypatch.setattr(GenerateStrategies, "load_experience_log", lambda *a, **k: "")
    return chat, RunPlantedSignal.generate_blueprints(n, "ollama-local")


def test_planted_step_corrects_slot_free_blueprint_once(monkeypatch):
    chat, accepted = run_planted(monkeypatch, [reply(NO_SLOT, "A"), json.dumps({"macro_blueprint": NOT_AN_EXAMPLE})])
    assert [b["macro_blueprint"] for b in accepted] == [NOT_AN_EXAMPLE]
    assert "no `?` slot" in chat.prompts[1]


def test_planted_step_drops_blueprint_still_slot_free_after_correction(monkeypatch, capsys):
    replies = [reply(NO_SLOT, "A"), json.dumps({"macro_blueprint": NO_SLOT}), "", "", ""]
    _, accepted = run_planted(monkeypatch, replies)
    assert accepted == []
    assert "rejected" in capsys.readouterr().out


def test_correction_prompt_mentions_slot_rule():
    assert "`?`" in build_correction_prompt("{}", "no slot")
