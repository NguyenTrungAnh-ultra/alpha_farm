import json
import re
from itertools import product

import numpy as np
import pandas as pd
import pytest

from strategy_workflows import LLMOnly as lo
from strategy_workflows import WalkForward as wf
from strategy_workflows.MCTSEngine import MCTSEngine
from tests.test_batched_blueprints import FakeChat
from tests.test_walk_forward import SMALL, hourly_frame
from utilities.Prompts import (
    FORMULA_DIMENSION_RULES, FORMULA_EXAMPLES, build_formula_batch_prompt, build_formula_correction_prompt,
)

MARKET_NAME = re.compile(r"vn30|vietnam|viet nam|\bhose\b|hanoi|ho chi minh", re.IGNORECASE)
PERIODS = [2, 3, 5, 10]
FIELDS = ("pv_open", "pv_high", "pv_low", "pv_close")
ROLLING = ("ts_mean", "ts_sum", "ts_max", "ts_min")


def formulas(n, start=0):
    """n distinct valid formulas (price fields only, windows from the 60m ladder), none a prompt example."""
    out = []
    for outer, a, b, f1, f2, w1, w2 in product(("sub", "add"), ROLLING, ROLLING, FIELDS, FIELDS, PERIODS, PERIODS):
        text = f"{outer}({a}({f1}, {w1}), {b}({f2}, {w2}))"
        if text not in FORMULA_EXAMPLES:
            out.append(text)
    return out[start:start + n]


def reply(texts, prefix="F"):
    return json.dumps({"ideas": [{"name": f"{prefix}{i}", "family": "x", "description": "d", "formula": t}
                                 for i, t in enumerate(texts)]})


def fix_reply(texts):
    return json.dumps({"ideas": [{"formula": t} for t in texts]})


# --- parsing and validation ---------------------------------------------------

def test_parse_formula_moves_windows_into_the_tree_and_picks_the_template():
    parsed = lo.parse_formula("sub(pv_close, ts_mean(pv_close, 10))")
    assert parsed.template == "NORMALIZED" and parsed.expr == "(close - ts_mean(close, 10))"
    assert parsed.tree.name == "normalized_template"
    assert lo.parse_formula("ts_corr(pv_close, pv_volume, 5)").template == "RATIO"
    boolean = lo.parse_formula("greater_than(ts_mean(pv_close, 3), pv_close)")
    assert boolean.template == "BOOLEAN" and boolean.tree.name == "greater_than"


@pytest.mark.parametrize("text, fragment", [
    ("sub(pv_close, ts_mean(?, 10))", "must not contain `?`"),
    ("ts_mean(pv_close)", "LAST argument"),
    ("ts_mean(pv_close, 4)", "not one of"),
    ("ts_mean(pv_close, 10.0)", "not one of"),
    ("ts_mean(10, pv_close)", "LAST argument"),
    ("ts_mean(pv_close, 10, 5)", "exactly one window"),
    ("add(pv_close, 3)", "number as an argument"),
    ("ts_corr(pv_close, 5)", "series argument"),
    ("ts_mean(ts_mean(ts_mean(ts_mean(pv_close, 2), 2), 2), 2)", "deeper than 3"),
    ("add(pv_close, pv_volume)", "incompatible"),
    ("ema(pv_close, 5)", "Unknown operator"),
    ("", "empty"),
])
def test_parse_formula_rejects_with_a_message_for_the_model(text, fragment):
    with pytest.raises(lo.FormulaError, match=fragment):
        lo.parse_formula(text)


def test_depth_limit_is_three_function_levels_under_a_numeric_template_and_four_for_a_boolean_root():
    assert lo.parse_formula("ts_mean(ts_mean(ts_mean(pv_close, 2), 2), 2)")
    assert lo.parse_formula("greater_than(ts_mean(ts_mean(ts_mean(pv_close, 2), 2), 2), pv_close)")
    with pytest.raises(lo.FormulaError):
        lo.parse_formula("greater_than(ts_mean(ts_mean(ts_mean(ts_mean(pv_close, 2), 2), 2), 2), pv_close)")


def test_prompt_examples_are_valid_formulas_and_the_prompt_names_no_market_and_lists_the_ladder():
    for text in FORMULA_EXAMPLES:
        lo.parse_formula(text)
    prompt = build_formula_batch_prompt("60m", 10, PERIODS, avoid=["add(pv_open, pv_high)"])
    assert not MARKET_NAME.search(prompt)
    assert "2, 3, 5, 10" in prompt and "`add(pv_open, pv_high)`" in prompt and "{n}" not in prompt
    assert "`?`" not in FORMULA_DIMENSION_RULES
    assert "2, 3, 5, 10" in build_formula_correction_prompt([("x", "bad")], PERIODS)
    with pytest.raises(ValueError):
        build_formula_batch_prompt("10m", 10, PERIODS)


def test_window_ladder_at_60m_is_the_engines():
    assert lo.window_ladders()[0] == PERIODS


# --- template grid and scoring ------------------------------------------------

def test_template_grid_enumerates_mcts_action_sets():
    periods, windows = lo.window_ladders()
    assert len(windows) == 5
    grid = lo.template_grid(lo.parse_formula("ts_mean(pv_close, 5)").tree, windows, periods)
    assert len(grid) == len(windows) * 5
    values = {(t.children[1].value, t.children[2].value) for t in grid}
    assert values == set(product(windows, [0.5, 1.0, 1.5, 2.0, 2.5]))
    ratio = lo.template_grid(lo.parse_formula("ts_zscore(pv_close, 5)").tree, windows, periods)
    assert {(t.children[1].value, t.children[2].value) for t in ratio} == set(
        product([60.0, 65.0, 70.0, 75.0, 80.0], [20.0, 25.0, 30.0, 35.0, 40.0]))
    assert len(lo.template_grid(lo.parse_formula("greater_than(pv_close, pv_open)").tree, windows, periods)) == 1
    assert wf.template_grid_sizes() == {"NORMALIZED": 25, "RATIO": 25, "BOOLEAN": 1}


def make_engine(seed=1):
    frame = hourly_frame()
    return MCTSEngine(timeframe="60m", seed=seed, data=frame.loc[:SMALL.train_end], reward_mode="sharpe",
                      global_position_matrix=None)


def test_score_formulas_keeps_the_best_parameters_of_each_formula_and_counts_grid_evaluations():
    engine = make_engine()
    items = [{"name": f"F{i}", "formula": t} for i, t in enumerate(
        ["sub(pv_close, ts_mean(pv_close, 5))", "ts_zscore(pv_close, 3)", "greater_than(pv_close, pv_open)"])]
    out = lo.score_formulas(engine, items)
    assert out == {"formulas": 3, "rejected": 0, "evaluations": 25 + 25 + 1}
    assert len(engine.leaderboard) == 3
    for item in items:
        parsed = lo.parse_formula(item["formula"])
        rewards = [engine.evaluate_expression(t)[0] for t in
                   lo.template_grid(parsed.tree, engine.scaled_window_search, engine.scaled_periods)]
        entry = next(e for e in engine.leaderboard if e["expr"] == parsed.expr)
        assert entry["reward"] == pytest.approx(max(rewards))
        if parsed.template == "NORMALIZED":
            assert len(set(rewards)) > 1            # parameters matter, so keeping the best is a real choice


def test_score_formulas_skips_a_formula_that_no_longer_parses():
    engine = make_engine()
    out = lo.score_formulas(engine, [{"name": "bad", "formula": "ts_mean(pv_close, 4)"},
                                     {"name": "ok", "formula": "ts_mean(pv_close, 5)"}])
    assert out["rejected"] == 1 and out["evaluations"] == 25 and len(engine.leaderboard) == 1


# --- generation ---------------------------------------------------------------

def test_hundred_formulas_in_ten_batched_requests_with_fixed_seed_and_temperature():
    texts = formulas(100)
    chat = FakeChat([reply(texts[i:i + 10], f"B{i}_") for i in range(0, 100, 10)])
    options = {"temperature": 0.3, "seed": 7}
    accepted, stats, prompt = lo.generate_formula_set(chat, 100, 10, options, model="ollama-9b")
    assert [a["formula"] for a in accepted] == texts and len(chat.prompts) == 10
    assert stats.requests == 10 and stats.n_accepted == 100 and stats.ideas == 100
    assert [o["seed"] for o in chat.options] == list(range(7, 17))
    assert all(o["temperature"] == 0.3 for o in chat.options)
    assert len({a["name"] for a in accepted}) == 100
    assert not MARKET_NAME.search(" ".join(chat.prompts))
    assert "`" + texts[0] + "`" in chat.prompts[1] and texts[0] not in chat.prompts[0] and prompt == chat.prompts[0]


def test_rejected_formulas_get_one_correction_request_and_duplicates_are_refused():
    texts = formulas(12)
    bad = "ts_mean(pv_close, 4)"
    first = reply(texts[:4] + [bad, texts[0]])             # one invalid window, one repeat of an accepted formula
    chat = FakeChat([first, fix_reply([texts[4], texts[1]]), reply(texts[5:7])])
    accepted, stats, _ = lo.generate_formula_set(chat, 6, 6, {"seed": 1}, model="ollama-9b", max_batches=3)
    # the correction fixes the invalid one; the repeat is "fixed" into another repeat and stays out
    assert [a["formula"] for a in accepted] == texts[:5] + [texts[5]]
    assert stats.duplicate_rejections == 2 and stats.requests == 3
    assert "ts_mean(pv_close, 4)" in chat.prompts[1] and "2, 3, 5, 10" in chat.prompts[1]


def test_a_prompt_example_is_refused_as_a_copy():
    texts = formulas(3)
    chat = FakeChat([reply([FORMULA_EXAMPLES[0]] + texts)])
    accepted, stats, _ = lo.generate_formula_set(chat, 3, 4, None, model="ollama-9b", max_batches=1)
    assert [a["formula"] for a in accepted] == texts and stats.example_copy_rejections == 1


def test_top_up_requests_stop_at_the_batch_limit():
    texts = formulas(10)
    chat = FakeChat([reply(texts[:3]), reply([]), reply(texts[3:5])])
    accepted, stats, _ = lo.generate_formula_set(chat, 10, 10, None, model="ollama-9b", max_batches=3)
    assert len(accepted) == 5 and len(chat.prompts) == 3


def test_build_writes_the_set_with_hashes_only_when_complete(tmp_path):
    texts = formulas(20)
    chat = FakeChat([reply(texts[:10], "A"), reply(texts[10:], "B")])
    out = tmp_path / "set"
    assert lo.build_formula_set(chat, str(out), n=20, batch=10, model="ollama-9b", seed=5) is True
    saved = json.loads((out / "formulas.json").read_text(encoding="utf-8"))
    record = json.loads((out / "generation.json").read_text(encoding="utf-8"))
    import hashlib
    assert [s["formula"] for s in saved] == texts
    assert record["formulas_sha256"] == hashlib.sha256((out / "formulas.json").read_bytes()).hexdigest()
    assert record["seed"] == 5 and record["temperature"] == 0.3 and record["windows"] == PERIODS
    assert record["stats"]["requests"] == 2 and record["n"] == 20 and len(record["prompt_sha256"]) == 64
    short = tmp_path / "short"
    assert lo.build_formula_set(FakeChat([reply(texts[:7])]), str(short), n=20, batch=10, model="ollama-9b") is False
    assert not short.exists()


def test_verify_formula_set_flags_a_duplicate_a_bad_formula_and_a_wrong_count():
    items = [{"name": "a", "formula": "ts_mean(pv_close, 5)"}, {"name": "b", "formula": "ts_mean(pv_close, 5)"},
             {"name": "c", "formula": "ts_mean(pv_close, 4)"}]
    problems = lo.verify_formula_set(items, 5)
    assert any("same expression as a" in p for p in problems) and any(p.startswith("c:") for p in problems)
    assert any("3 formulas, expected 5" in p for p in problems)
    assert lo.verify_formula_set(items[:1], 1) == []


def test_cli_build_step_exists_and_defaults_to_100_in_batches_of_10():
    import argparse
    parser = argparse.ArgumentParser()
    lo.add_llm_only_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["llmonly", "build"])
    assert (args.n, args.batch_size, args.seed) == (100, 10, lo.LLM_ONLY_SEED)


# --- in a walk-forward window -------------------------------------------------

LLM_FORMULAS = [{"name": f"F{i}", "formula": t} for i, t in enumerate(formulas(6, 40))]


def llm_only_task(mode="real", k=0, seed=1):
    return {"mode": mode, "placebo_set": k, "window": 1, "seed": seed, "segments": SMALL, "frame": hourly_frame(),
            "data_seed": wf.placebo_seed(k, 1) if k else 0, "iterations": 20, "blueprints": [],
            "system": "llm_only", "plan": wf.wf_plan(), "llm": None, "formulas": LLM_FORMULAS}


def test_llm_only_window_scores_every_formula_over_the_grid_and_records_the_evaluation_count():
    out = wf.run_window(llm_only_task())
    row = out["row"]
    assert row["system"] == "llm_only" and set(wf.RUN_FIELDS) == set(row)
    assert row["evaluations"] == row["iterations"] == 25 * 6 == json.loads(row["info"])["grid_evaluations"]
    assert row["llm_requests"] == 0 and row["n_ranked"] == 6 and 1 <= row["n_top"] <= 5
    assert out["returns"].index.min() >= pd.Timestamp(SMALL.eval_start)
    assert wf.run_window(llm_only_task())["row"]["top"] == row["top"]


def test_llm_only_runs_seed_1_only_and_other_systems_keep_their_seeds():
    frame = hourly_frame()
    only = wf.build_tasks("real", [SMALL, SMALL], [1, 2, 3, 4, 5], [], 5, frame, system="llm_only",
                          formulas=LLM_FORMULAS)
    assert sorted({t["seed"] for t in only}) == [1] and len(only) == 2
    assert all(t["formulas"] is LLM_FORMULAS for t in only)
    other = wf.build_tasks("real", [SMALL], [1, 2, 3, 4, 5], [], 5, frame, system="random")
    assert sorted(t["seed"] for t in other) == [1, 2, 3, 4, 5]
    assert wf.seeds_for("tsmom", [1, 2, 3]) == [1] and wf.seeds_for("llm_mcts", [1, 2, 3]) == [1, 2, 3]


def test_llm_only_gives_identical_results_for_any_seed():
    one = wf.run_window(llm_only_task(seed=1))
    two = wf.run_window(llm_only_task(seed=2))
    assert one["row"]["top"] == two["row"]["top"] and one["row"]["eval_sharpe"] == two["row"]["eval_sharpe"]
    np.testing.assert_allclose(one["returns"].to_numpy(), two["returns"].to_numpy())
