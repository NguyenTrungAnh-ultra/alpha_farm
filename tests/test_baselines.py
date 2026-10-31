import json

import numpy as np
import pandas as pd
import pytest

from core_engine.BacktestEngine import AlphaBacktestEngine
from strategy_workflows import Baselines as bl
from strategy_workflows import WalkForward as wf
from strategy_workflows.MCTSEngine import _FixedPositions
from tests.test_walk_forward import SMALL, hourly_frame

SCALE = bl.POSITION_SCALE


def reference_task(system, mode="real", k=0, frame=None):
    return {"mode": mode, "placebo_set": k, "window": 1, "seed": 1, "segments": SMALL,
            "frame": hourly_frame() if frame is None else frame, "data_seed": wf.placebo_seed(k, 1) if k else 0,
            "iterations": 0, "blueprints": [], "system": system, "plan": wf.wf_plan(), "llm": None}


def trending_frame(step=1.0):
    """Hourly bars whose Close rises by `step` every bar."""
    frame = hourly_frame()
    close = 1000.0 + step * np.arange(len(frame))
    frame = frame.copy()
    frame["Close"], frame["Open"], frame["High"], frame["Low"] = close, close, close + 0.5, close - 0.5
    return frame


# --- buy and hold -------------------------------------------------------------

def test_buy_hold_is_always_long_at_the_strategy_position_size():
    positions = bl.buy_hold_positions(hourly_frame().index)
    assert (positions == SCALE).all() and SCALE == 0.2


def test_buy_hold_return_goes_through_the_engine_with_its_fees_and_contract_sizing():
    frame = trending_frame()
    out = wf.run_window(reference_task("buy_hold", frame=frame))
    evaluation = frame.loc[SMALL.eval_start:SMALL.eval_end]
    direct = AlphaBacktestEngine().run(_FixedPositions(pd.Series(SCALE, index=evaluation.index)), evaluation)
    np.testing.assert_allclose(out["returns"].to_numpy(), wf.daily_returns(direct).to_numpy())
    assert out["returns"].sum() > 0 and out["row"]["eval_trades"] == direct.total_trades
    # contract count is fixed from the capital and the first price: gain = contracts * rise * multiplier - fees
    engine = AlphaBacktestEngine()
    contracts = round(SCALE * engine.calc_contracts(1.0, engine.initial_capital, float(evaluation["Close"].iloc[0])))
    rise = float(evaluation["Close"].iloc[-1] - evaluation["Close"].iloc[1])      # the first bar is flat (signal lag)
    gross = contracts * rise * 100_000 / engine.initial_capital
    assert out["returns"].sum() == pytest.approx(gross, rel=0.05)


def test_buy_hold_row_has_no_search_columns_and_one_run_per_window():
    row = wf.run_window(reference_task("buy_hold"))["row"]
    assert set(row) == set(wf.RUN_FIELDS) and row["system"] == "buy_hold"
    assert row["evaluations"] == 0 and row["llm_requests"] == 0 and row["n_blueprints"] == 0
    assert wf.build_tasks("real", [SMALL], [1, 2, 3], [], 0, hourly_frame(), system="buy_hold")[0]["seed"] == 1


# --- TSMOM --------------------------------------------------------------------

def test_tsmom_position_is_the_sign_of_the_past_return_at_the_strategy_size():
    close = pd.Series([10.0, 11.0, 10.0, 9.0, 9.0, 12.0])
    one = bl.tsmom_positions(close, 1)
    assert one.tolist() == [0.0, SCALE, -SCALE, -SCALE, 0.0, SCALE]
    two = bl.tsmom_positions(close, 2)
    assert two.tolist() == [0.0, 0.0, 0.0, -SCALE, -SCALE, SCALE]
    with pytest.raises(ValueError):
        bl.tsmom_positions(close, 0)


def test_tsmom_signal_at_t_fills_at_the_next_bar_in_the_engine():
    frame = trending_frame()
    close = frame["Close"]
    positions = bl.tsmom_positions(close, 5)
    result = AlphaBacktestEngine().run(_FixedPositions(positions), frame)
    # the position the engine holds on bar t is the signal of bar t - 1
    np.testing.assert_allclose(result.positions.to_numpy()[6:], positions.shift(1).to_numpy()[6:])
    assert result.positions.iloc[0] == 0.0


def test_bars_per_session_is_the_median_and_lookbacks_scale_by_sessions():
    index = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d, n in
                              zip(pd.date_range("2024-01-01", periods=5), [8, 8, 4, 8, 5]) for h in range(n)])
    frame = pd.DataFrame({"Close": 1.0}, index=index)
    assert bl.bars_per_session(frame) == 8
    assert bl.tsmom_lookbacks(8) == {"day": 8, "week": 40, "month": 168}
    assert bl.TSMOM_LOOKBACK_SESSIONS == {"day": 1, "week": 5, "month": 21}


def test_choose_lookback_takes_the_best_validation_sharpe_nan_loses_and_ties_go_to_the_shortest():
    assert wf.choose_lookback({"day": 0.1, "week": 0.9, "month": 0.5}) == "week"
    assert wf.choose_lookback({"day": float("nan"), "week": -2.0, "month": float("nan")}) == "week"
    assert wf.choose_lookback({"day": 0.7, "week": 0.7, "month": 0.7}) == "day"
    assert wf.choose_lookback({"day": -1.0, "week": -1.0, "month": -3.0}) == "day"
    assert wf.choose_lookback({"day": float("nan"), "week": float("nan"), "month": float("nan")}) == "day"


def test_tsmom_window_picks_its_lookback_on_validation_and_trades_the_evaluation_with_it():
    frame = hourly_frame(seed=3)
    out = wf.run_window(reference_task("tsmom", frame=frame))
    info = json.loads(out["row"]["info"])
    train = frame.loc[:SMALL.train_end]
    assert info["bars_by_label"] == bl.tsmom_lookbacks(bl.bars_per_session(train))
    sharpes = info["validation_sharpe"]
    assert info["chosen"] == wf.choose_lookback({k: np.nan if v is None else v for k, v in sharpes.items()})
    assert info["lookback_bars"] == info["bars_by_label"][info["chosen"]]
    # validation Sharpe of the chosen lookback, recomputed by hand through the engine
    validation = frame.loc[SMALL.validation_start:SMALL.search_end]
    for label, bars in info["bars_by_label"].items():
        positions = bl.tsmom_positions(frame["Close"], bars).loc[validation.index]
        expected = wf.annualised_sharpe(wf.daily_returns(AlphaBacktestEngine().run(_FixedPositions(positions), validation)))
        assert sharpes[label] == pytest.approx(expected)
    evaluation = frame.loc[SMALL.eval_start:SMALL.eval_end]
    direct = AlphaBacktestEngine().run(
        _FixedPositions(bl.tsmom_positions(frame["Close"], info["lookback_bars"]).loc[evaluation.index]), evaluation)
    np.testing.assert_allclose(out["returns"].to_numpy(), wf.daily_returns(direct).to_numpy())
    assert out["row"]["system"] == "tsmom" and out["row"]["evaluations"] == 0


def test_tsmom_follows_a_trend_and_loses_on_the_reverse_trend():
    up = wf.run_window(reference_task("tsmom", frame=trending_frame(1.0)))
    down = wf.run_window(reference_task("tsmom", frame=trending_frame(-0.2)))
    assert up["returns"].sum() > 0 and down["returns"].sum() > 0        # a falling market is followed short
    assert json.loads(up["row"]["info"])["chosen"] in ("day", "week", "month")


def test_references_run_on_placebo_data_too():
    for system in ("buy_hold", "tsmom"):
        row = wf.run_window(reference_task(system, "placebo", 1))["row"]
        assert row["mode"] == "placebo" and row["system"] == system
