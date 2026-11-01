import hashlib
import json
import time

import numpy as np
import pandas as pd
import pytest

from strategy_workflows import SearchConfigs as sc
from strategy_workflows.MCTSEngine import MCTSEngine
from strategy_workflows.PlantedSignal import Segments
from tests.test_batched_blueprints import batch_reply, correction_reply, skeletons

INITIAL = [{"name": f"Init{i}", "macro_blueprint": bp} for i, bp in enumerate(skeletons(16)[:4])]
NEW_SKELETONS = skeletons(16)[4:7]
SEGMENTS = Segments(search_start='2024-01-01', train_end='2024-01-20', search_end='2024-02-05', eval_end='2024-02-10')
PLAN = sc.BudgetPlan(total=120, phase_a=60, chunk=10, checkpoints=(20, 60, 120), feedback_expressions=4,
                     feedback_blueprints=3)

LEAN = sc.BudgetPlan(total=120, phase_a=60, chunk=10, checkpoints=(), feedback_expressions=4, feedback_blueprints=3)


@pytest.fixture(scope='module')
def frame():
    rng = np.random.default_rng(8)
    index = pd.date_range('2024-01-01', '2024-02-10 23:00', freq='h', name='Datetime')
    close = 1000.0 * np.cumprod(1.0 + rng.normal(0.0, 0.002, len(index)))
    return pd.DataFrame({
        'Open': close * rng.uniform(0.999, 1.001, len(index)), 'High': close * rng.uniform(1.0, 1.003, len(index)),
        'Low': close * rng.uniform(0.997, 1.0, len(index)), 'Close': close,
        'Volume': rng.uniform(1000, 5000, len(index)),
    }, index=index)


class SlowChat:
    """FakeChat that takes a little time and can report when it is asked."""
    model, host = "fake", "http://fake"

    def __init__(self, replies, on_send=None):
        self.replies, self.prompts, self.options, self.on_send = list(replies), [], [], on_send

    def send(self, prompt, schema=None, options=None):
        if self.on_send:
            self.on_send()
        time.sleep(0.02)
        self.prompts.append(prompt)
        self.options.append(options)
        return self.replies.pop(0) if self.replies else ""


def feedback_replies():
    return [batch_reply(NEW_SKELETONS, "New")]


def new_engine(frame, seed=5):
    return MCTSEngine(timeframe='60m', data=frame.loc[:SEGMENTS.train_end], seed=seed, reward_mode='sharpe',
                      global_position_matrix=None)


def run(system, frame, plan=PLAN, chat=None, seed=5, run_key='k', on_chunk=None, blueprints=INITIAL):
    engine = new_engine(frame, seed)
    outcome = sc.run_search(system, engine, frame.loc[:SEGMENTS.search_end], SEGMENTS, plan, blueprints, run_key,
                            chat, 'ollama-9b', on_chunk)
    return engine, outcome


def picked_summary(picked):
    return [(picked['ranked'][i]['expr'], picked['val_rewards'][i]) for i in picked['chosen']]


def board(engine):
    return [(c['expr'], c['reward'], c['direction']) for c in engine.leaderboard]


# --- helpers ----------------------------------------------------------------

def test_split_evenly_spends_everything_and_gives_the_larger_shares_first():
    assert sc.split_evenly(100_000, 3) == [33334, 33333, 33333]
    assert sc.split_evenly(50_000, 20) == [2500] * 20
    assert sc.split_evenly(50_000, 7) == [7143] * 6 + [7142]
    assert sc.split_evenly(5, 0) == []
    assert sum(sc.split_evenly(1234, 9)) == 1234


def test_llm_seed_is_stable_in_range_and_depends_on_the_run_key():
    assert sc.llm_seed("wf|real|0|3|2") == sc.llm_seed("wf|real|0|3|2")
    assert sc.llm_seed("wf|real|0|3|2") != sc.llm_seed("wf|real|0|3|3")
    assert 0 <= sc.llm_seed("anything") < 2 ** 31
    assert sc.llm_seed("x") == int.from_bytes(hashlib.sha256(b"x").digest()[:4], "big") & 0x7FFFFFFF


def test_expression_text_uses_blueprint_notation_without_windows():
    assert sc.expression_to_blueprint_text("(close - ts_mean(close, 10))") == "sub(pv_close, ts_mean(pv_close))"
    assert sc.expression_to_blueprint_text("(open_ * ts_zscore(volume, 5))") == "mult(pv_open, ts_zscore(pv_volume))"
    assert sc.expression_to_blueprint_text("ts_corr(close, volume, 20)") == "ts_corr(pv_close, pv_volume)"
    assert sc.expression_to_blueprint_text("(high / (low + 1e-8))") == "div(pv_high, pv_low)"
    assert sc.expression_to_blueprint_text("(0.5 + close)") == "add(0.5, pv_close)"
    assert sc.expression_to_blueprint_text("not valid ((") == "not valid (("


def test_budget_clock_fires_each_checkpoint_once_in_order():
    fired = []
    clock = sc.BudgetClock((30, 10, 60), lambda budget, spent: fired.append((budget, spent)))
    for amount in (5, 5, 20, 40, 10):
        clock.tick(amount)
    assert fired == [(10, 10), (30, 30), (60, 70)] and clock.spent == 80


def test_timer_does_not_count_measurement_time():
    timer = sc.SearchTimer()
    time.sleep(0.05)
    with timer.measuring():
        time.sleep(0.2)
    assert 0.04 < timer.elapsed() < 0.18


def test_feedback_items_are_the_best_distinct_train_expressions(frame):
    engine, _ = run('mcts_only', frame, sc.BudgetPlan(total=120, phase_a=0, chunk=20, checkpoints=()))
    items = sc.feedback_items(engine, 4)
    assert len(items) == 4
    rewards = [item['reward'] for item in items]
    assert rewards == sorted(rewards, reverse=True)
    assert len({item['expression'] for item in items}) == 4
    best = max(engine.leaderboard, key=lambda c: c['reward'])
    assert items[0]['reward'] == best['reward']
    assert items[0]['rank_ic'] == pytest.approx(best['metrics']['rank_ic'])


# --- llm_mcts ---------------------------------------------------------------

def test_llm_mcts_runs_phase_a_then_feedback_then_phase_b_on_the_new_blueprints(frame):
    spent_at_send = []
    last = {'spent': 0}
    chat = SlowChat(feedback_replies(), on_send=lambda: spent_at_send.append(last['spent']))
    engine = new_engine(frame)
    log = []
    original = engine.continue_search

    def logging(session, n, *args, **kwargs):
        before = session.iterations
        result = original(session, n, *args, **kwargs)
        log.append((id(session), session.iterations - before))
        return result

    engine.continue_search = logging
    outcome = sc.run_search('llm_mcts', engine, frame.loc[:SEGMENTS.search_end], SEGMENTS, PLAN, INITIAL, 'run-1', chat,
                            'ollama-9b', lambda eng, spent, wall: last.update(spent=spent))

    assert outcome.iterations == PLAN.total and outcome.stop_reasons == {'budget': 7}
    assert spent_at_send == [PLAN.phase_a]                       # asked once, right after phase A
    per_session = {}
    for key, ran in log:
        per_session[key] = per_session.get(key, 0) + ran
    first_four = list(dict.fromkeys(key for key, _ in log))
    assert [per_session[k] for k in first_four] == [15] * 4 + [20] * 3
    assert sum(ran for _, ran in log[:8]) == 60                 # 4 sessions x 15 (chunks of 10 and 5) come first
    assert [b['macro_blueprint'] for b in outcome.new_blueprints] == NEW_SKELETONS
    assert outcome.feedback['n_new'] == 3 and outcome.feedback['fallback'] is False
    assert outcome.feedback['prompt_sha256'] == hashlib.sha256(chat.prompts[0].encode('utf-8')).hexdigest()
    assert outcome.llm_requests == 1 and outcome.llm_s >= 0.02


def test_checkpoints_are_taken_at_the_planned_budgets_with_growing_clocks(frame):
    chat = SlowChat(feedback_replies())
    _, outcome = run('llm_mcts', frame, chat=chat)
    records = outcome.checkpoints
    assert [r['budget'] for r in records] == [20, 60, 120] == [r['iterations'] for r in records]
    assert [r['wall_s'] for r in records] == sorted(r['wall_s'] for r in records)
    assert [r['evaluations'] for r in records] == sorted(r['evaluations'] for r in records)
    assert records[0]['llm_s'] == records[1]['llm_s'] == 0.0     # the 60 checkpoint is before the feedback round
    assert records[2]['llm_s'] > 0 and records[2]['llm_requests'] == 1
    assert outcome.final is records[-1]['picked']


def test_checkpoints_do_not_change_the_search_so_the_final_top5_matches_the_run_without_them(frame):
    with_cp_engine, with_cp = run('llm_mcts', frame, chat=SlowChat(feedback_replies()))
    plain = sc.BudgetPlan(total=PLAN.total, phase_a=PLAN.phase_a, chunk=PLAN.chunk, checkpoints=(),
                          feedback_expressions=4, feedback_blueprints=3)
    plain_engine, without = run('llm_mcts', frame, plain, chat=SlowChat(feedback_replies()))
    assert without.checkpoints == []
    assert picked_summary(with_cp.final) == picked_summary(without.final)
    assert with_cp.final['chosen'] == without.final['chosen']
    assert board(with_cp_engine) == board(plain_engine)
    assert with_cp_engine.evaluation_count == plain_engine.evaluation_count


def test_intermediate_checkpoint_equals_a_run_that_stops_at_that_budget(frame):
    # same schedule, budget cut at 60: the ranking at the 60 checkpoint of the long run is identical
    _, long_run = run('llm_mcts', frame, chat=SlowChat(feedback_replies()))
    short_plan = sc.BudgetPlan(total=60, phase_a=60, chunk=10, checkpoints=(60,), feedback_expressions=4,
                               feedback_blueprints=3)
    _, short = run('llm_mcts', frame, short_plan, chat=SlowChat([]))
    at_60 = next(r for r in long_run.checkpoints if r['budget'] == 60)
    assert picked_summary(at_60['picked']) == picked_summary(short.checkpoints[0]['picked'])


def test_fewer_new_blueprints_share_phase_b_evenly(frame):
    two = [batch_reply(NEW_SKELETONS[:2], "New")]
    engine = new_engine(frame)
    seen = []
    original = engine.continue_search
    engine.continue_search = lambda session, n, *a, **k: (seen.append(id(session)), original(session, n, *a, **k))[1]
    outcome = sc.run_search('llm_mcts', engine, frame.loc[:SEGMENTS.search_end], SEGMENTS,
                            sc.BudgetPlan(total=130, phase_a=60, chunk=10, checkpoints=(), feedback_expressions=4,
                                          feedback_blueprints=3), INITIAL, 'k', SlowChat(two), 'ollama-9b')
    assert outcome.iterations == 130 and len(outcome.new_blueprints) == 2
    assert [seen.count(k) for k in dict.fromkeys(seen)] == [2] * 4 + [4, 4]  # 60/4 = 15 each in 2 chunks; 70 over 2 = 35 each in 4 chunks


def test_no_accepted_feedback_blueprint_sends_phase_b_to_the_initial_blueprints(frame):
    engine = new_engine(frame)
    seen = []
    original = engine.continue_search
    engine.continue_search = lambda session, n, *a, **k: (seen.append((id(session), session.iterations)),
                                                          original(session, n, *a, **k))[1]
    outcome = sc.run_search('llm_mcts', engine, frame.loc[:SEGMENTS.search_end], SEGMENTS, LEAN, INITIAL, 'k',
                            SlowChat(["", ""]), 'ollama-9b')
    assert outcome.iterations == 120 and outcome.new_blueprints == []
    assert outcome.feedback['fallback'] is True and outcome.feedback['n_new'] == 0
    assert len(set(key for key, _ in seen)) == 4                 # only the four initial sessions ever ran
    assert max(done for _, done in seen) == 25                   # each reaches 30 = 120 / 4: its last chunk starts at 25


def test_no_scored_expression_means_no_llm_call(frame):
    chat = SlowChat(feedback_replies())
    plan = sc.BudgetPlan(total=0, phase_a=0, chunk=10, checkpoints=())
    _, outcome = run('llm_mcts', frame, plan, chat=chat, blueprints=[])
    assert chat.prompts == [] and outcome.feedback['n_scored'] == 0 and outcome.feedback['fallback'] is True


def test_llm_requests_are_seeded_from_the_run_key(frame):
    def options_for(key):
        chat = SlowChat([batch_reply(["bad_op(?)"]), "garbage"])
        run('llm_mcts', frame, LEAN, chat=chat, run_key=key)
        return chat.options

    first = options_for('wf|real|0|1|1')
    assert first == options_for('wf|real|0|1|1')
    assert first != options_for('wf|real|0|1|2')
    seed = sc.llm_seed('wf|real|0|1|1|feedback')
    assert first[0]['seed'] == seed and first[1]['seed'] == seed + 1      # advances per request


def test_same_run_gives_the_same_prompt_and_blueprints(frame):
    chats = [SlowChat(feedback_replies()) for _ in range(2)]
    outcomes = [run('llm_mcts', frame, LEAN, chat=chat, run_key='same')[1] for chat in chats]
    assert chats[0].prompts == chats[1].prompts
    assert outcomes[0].feedback['prompt_sha256'] == outcomes[1].feedback['prompt_sha256']


def test_the_feedback_prompt_has_train_numbers_only(frame):
    chat = SlowChat(feedback_replies())
    engine, outcome = run('llm_mcts', frame, chat=chat)
    prompt = chat.prompts[0]
    import re
    shown = [float(v) for v, _ in re.findall(r"reward (-?\d+\.\d+), rank IC ([+-]\d+\.\d+)", prompt)]
    at_phase_a = next(r for r in outcome.checkpoints if r['budget'] == PLAN.phase_a)
    assert 0 < len(shown) <= 4 and shown == sorted(shown, reverse=True)
    val_rewards = {round(v, 4) for v in at_phase_a['picked']['val_rewards']}
    train_rewards = {round(c['reward'], 4) for c in at_phase_a['picked']['ranked']}
    # every shown reward is a train reward; validation rewards that are not also train rewards never appear
    assert {round(v, 4) for v in shown} <= train_rewards
    assert not ((val_rewards - train_rewards) & {round(v, 4) for v in shown})
    for word in ("validation", "evaluation", "vn30"):
        assert word not in prompt.lower()


def test_llm_mcts_needs_a_chat_client(frame):
    with pytest.raises(ValueError, match="chat client"):
        run('llm_mcts', frame)


def test_unknown_system_is_refused(frame):
    with pytest.raises(ValueError, match="system"):
        run('oneshot', frame)


# --- mcts_only and random ---------------------------------------------------

def test_mcts_only_spends_the_budget_evenly_over_the_three_template_roots(frame):
    engine = new_engine(frame)
    seen = []
    original = engine.continue_search
    engine.continue_search = lambda session, n, *a, **k: (seen.append((id(session), n)),
                                                          original(session, n, *a, **k))[1]
    plan = sc.BudgetPlan(total=100, phase_a=0, chunk=10, checkpoints=(30, 100))
    outcome = sc.run_search('mcts_only', engine, frame.loc[:SEGMENTS.search_end], SEGMENTS, plan)
    totals = {}
    for key, n in seen:
        totals[key] = totals.get(key, 0) + n
    assert sorted(totals.values()) == [33, 33, 34] and outcome.iterations == 100
    assert [r['iterations'] for r in outcome.checkpoints] == [30, 100]
    templates = {c['template'] for c in engine.leaderboard}
    assert templates <= {'NORMALIZED', 'BOOLEAN', 'RATIO'} and len(templates) >= 2
    assert outcome.llm_requests == 0 and outcome.new_blueprints == []


def test_random_system_checkpoints_and_stats(frame):
    plan = sc.BudgetPlan(total=160, phase_a=0, chunk=20, checkpoints=(40, 160))
    engine, outcome = run('random', frame, plan)
    assert outcome.random_stats['samples'] == 160
    assert outcome.random_stats['per_depth'] == {1: 40, 2: 40, 3: 40, 4: 40}
    assert [r['iterations'] for r in outcome.checkpoints] == [40, 160]
    _, again = run('random', frame, plan)
    assert picked_summary(outcome.final) == picked_summary(again.final)


@pytest.mark.parametrize("system", ["mcts_only", "random"])
def test_checkpoints_do_not_change_the_other_systems_either(frame, system):
    with_cp = sc.BudgetPlan(total=120, phase_a=0, chunk=20, checkpoints=(20, 60, 120))
    without = sc.BudgetPlan(total=120, phase_a=0, chunk=20, checkpoints=())
    engine_a, a = run(system, frame, with_cp)
    engine_b, b = run(system, frame, without)
    assert picked_summary(a.final) == picked_summary(b.final)
    assert board(engine_a) == board(engine_b)


def test_on_chunk_runs_after_every_chunk_and_its_time_is_not_in_wall_time(frame):
    calls = []

    def hook(engine, spent, wall):
        calls.append((spent, wall))
        time.sleep(0.05)

    plan = sc.BudgetPlan(total=60, phase_a=0, chunk=20, checkpoints=())
    _, outcome = run('random', frame, plan, on_chunk=hook)
    assert [spent for spent, _ in calls] == [20, 40, 60]
    assert outcome.wall_s < 0.15 + 3 * 0.05 and all(w2 >= w1 for (_, w1), (_, w2) in zip(calls, calls[1:]))
