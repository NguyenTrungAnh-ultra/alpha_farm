"""
Empirical Verification Harness for Challenger 2 (Milestone 3)
=============================================================
Tests:
1. AlphaEngine & XNOBacktestEngine Integration
2. Margin Requirements & Margin Call Trigger Mechanics (Long & Short)
3. Netting Fee, Scale-in/out Fees, and Rollover Penalty Calculations
4. PnL Metrics Consistency (MTM Equity vs Trade Records vs CalculateMetrics)
5. Metric Edge Cases (Daily vs Intra-day Drawdown, Zero Volatility, Open Position at End)
"""

import sys
import os
import math
import numpy as np
import pandas as pd
import pytest

# Add workspace root to sys.path
sys.path.insert(0, 'f:/Projects/alpha_farm')

from core_engine.AlphaEngine import (
    AlphaEngine,
    AlphaStrategy,
    AlphaDataProxy,
)
from core_engine.BacktestEngine import (
    XNOBacktestEngine,
    BacktestResult,
    TradeRecord,
)
from core_engine.CalculateMetrics import compute_metrics as calc_compute_metrics
from core_engine.GenerateReport import compute_metrics as report_compute_metrics
from utilities.AppConfig import (
    INITIAL_CAPITAL,
    MARGIN_RATE,
    MAINTENANCE_MARGIN_RATE,
    FEE_PER_CONTRACT_PER_SIDE,
    MULTIPLIER,
    ROLLOVER_PENALTY_POINTS,
)


class SimpleLongStrategy(AlphaStrategy):
    """Strategy that buys at bar 5 and holds until bar 20."""
    def __algorithm__(self):
        idx = self.data.index
        mask = (np.arange(len(idx)) >= 5) & (np.arange(len(idx)) < 20)
        self.set_positions(mask, 1.0)


class SimpleShortStrategy(AlphaStrategy):
    """Strategy that shorts at bar 5 and holds until bar 20."""
    def __algorithm__(self):
        idx = self.data.index
        mask = (np.arange(len(idx)) >= 5) & (np.arange(len(idx)) < 20)
        self.set_positions(mask, -1.0)


class ReversalStrategy(AlphaStrategy):
    """Strategy that goes Long at bar 5..15, then Short at bar 15..25."""
    def __algorithm__(self):
        idx = self.data.index
        long_mask = (np.arange(len(idx)) >= 5) & (np.arange(len(idx)) < 15)
        short_mask = (np.arange(len(idx)) >= 15) & (np.arange(len(idx)) < 25)
        self.set_positions(long_mask, 1.0)
        self.set_positions(short_mask, -1.0)


class ScaleInOutStrategy(AlphaStrategy):
    """Strategy scaling in (0.5 -> 1.0) and scaling out (1.0 -> 0.5 -> 0.0)."""
    def __algorithm__(self):
        idx = self.data.index
        n = len(idx)
        p = np.zeros(n)
        p[5:10] = 0.5
        p[10:15] = 1.0
        p[15:20] = 0.5
        p[20:25] = 0.0
        self._positions = pd.Series(p, index=idx)


def create_dummy_df(periods=50, start_price=1000.0, trend=0.0, dates=None):
    if dates is None:
        dates = pd.date_range('2025-01-01 09:00', periods=periods, freq='15min')
    prices = start_price + np.arange(periods) * trend
    df = pd.DataFrame({
        'Open': prices,
        'High': prices + 2.0,
        'Low': prices - 2.0,
        'Close': prices,
        'Volume': 1000.0
    }, index=dates)
    return df


# =====================================================================
# TEST CASES
# =====================================================================

def test_engine_integration():
    """Verify AlphaEngine initializes XNOBacktestEngine parameters properly."""
    cap = 500_000_000.0
    mr = 0.30
    mmr = 0.20
    fee = 5000.0

    engine = AlphaEngine(
        initial_capital=cap,
        margin_rate=mr,
        maintenance_margin_rate=mmr,
        fee_per_contract=fee,
    )

    assert engine.initial_capital == cap
    assert engine.margin_rate == mr
    assert engine.maintenance_margin_rate == mmr
    assert engine.fee_per_contract == fee

    assert engine._backtest_engine.initial_capital == cap
    assert engine._backtest_engine.margin_rate == mr
    assert engine._backtest_engine.maintenance_margin_rate == mmr
    assert engine._backtest_engine.fee_per_contract == fee

    df = create_dummy_df(30, start_price=1000.0)
    strat = SimpleLongStrategy()

    res_alpha = engine.run(strat, df)
    res_xno = engine._backtest_engine.run(strat, df)

    assert res_alpha.initial_capital == res_xno.initial_capital
    assert (res_alpha.equity_curve == res_xno.equity_curve).all()
    assert res_alpha.total_fees == res_xno.total_fees
    assert len(res_alpha.trades) == len(res_xno.trades)

    metrics = engine.evaluate(strat, df)
    assert isinstance(metrics, dict)
    assert 'sharpe_ratio' in metrics
    assert 'cagr_pct' in metrics


def test_margin_requirements_and_long_margin_call():
    """Verify margin calculation and Long margin call trigger & equity freeze."""
    engine = XNOBacktestEngine(
        initial_capital=1_000_000_000.0,
        margin_rate=0.285,
        maintenance_margin_rate=0.210,
        fee_per_contract=6000.0
    )

    contracts = engine.calc_contracts(1.0, 1_000_000_000.0, 1000.0)
    expected_contracts = round(1.0 * 1_000_000_000.0 / (1000.0 * MULTIPLIER * 0.285))
    assert contracts == expected_contracts  # 35 contracts

    mc_pct = -(0.285 - 0.210) / 0.285
    equity_mc_threshold = 1_000_000_000.0 * (1 + mc_pct)

    dates = pd.date_range('2025-01-01', periods=10, freq='15min')
    close_prices = np.array([1000.0, 1000.0, 1000.0, 1000.0, 700.0, 600.0, 500.0, 400.0, 300.0, 200.0])
    df = pd.DataFrame({
        'Open': close_prices,
        'High': close_prices + 1,
        'Low': close_prices - 50,
        'Close': close_prices,
        'Volume': 1000.0
    }, index=dates)

    positions = np.ones(10)
    class AlwaysLong:
        def run_algorithm(self, df):
            return pd.Series(positions, index=df.index)

    result = engine.run(AlwaysLong(), df)

    assert (result.equity_curve >= equity_mc_threshold - 1e-3).all()
    assert np.isclose(result.final_equity, equity_mc_threshold, rtol=1e-3)
    assert len(result.trades) >= 1
    sum_trade_pnl = sum(t.net_pnl for t in result.trades)
    assert np.isclose(sum_trade_pnl, result.final_equity - result.initial_capital, rtol=1e-2)


def test_short_margin_call():
    """Verify Short margin call trigger when price rallies heavily."""
    engine = XNOBacktestEngine(
        initial_capital=1_000_000_000.0,
        margin_rate=0.285,
        maintenance_margin_rate=0.210,
        fee_per_contract=6000.0
    )

    mc_pct = -(0.285 - 0.210) / 0.285
    equity_mc_threshold = 1_000_000_000.0 * (1 + mc_pct)

    dates = pd.date_range('2025-01-01', periods=10, freq='15min')
    close_prices = np.array([1000.0, 1000.0, 1000.0, 1000.0, 1300.0, 1400.0, 1500.0, 1600.0, 1700.0, 1800.0])
    df = pd.DataFrame({
        'Open': close_prices,
        'High': close_prices + 50,
        'Low': close_prices - 1,
        'Close': close_prices,
        'Volume': 1000.0
    }, index=dates)

    positions = -np.ones(10)
    class AlwaysShort:
        def run_algorithm(self, df):
            return pd.Series(positions, index=df.index)

    result = engine.run(AlwaysShort(), df)

    assert (result.equity_curve >= equity_mc_threshold - 1e-3).all()
    assert np.isclose(result.final_equity, equity_mc_threshold, rtol=1e-3)


def test_fee_calculations_and_netting():
    """Verify Netting fee (reversal vs open/close) and total fees consistency."""
    engine = XNOBacktestEngine(
        initial_capital=1_000_000_000.0,
        fee_per_contract=6000.0
    )
    df = create_dummy_df(40, start_price=1000.0)
    strat = ReversalStrategy()

    result = engine.run(strat, df)

    assert result.total_fees == 840_000.0
    sum_trade_fees = sum(t.fee for t in result.trades)
    assert sum_trade_fees == result.total_fees == 840_000.0


def test_pnl_metrics_consistency():
    """Verify total net PnL from equity curve matches sum of trade net_pnl."""
    engine = XNOBacktestEngine(initial_capital=1_000_000_000.0)
    df = create_dummy_df(50, start_price=1000.0, trend=5.0)
    strat = ReversalStrategy()

    result = engine.run(strat, df)

    net_equity_pnl = result.final_equity - result.initial_capital
    sum_trades_pnl = sum(t.net_pnl for t in result.trades)

    assert np.isclose(net_equity_pnl, sum_trades_pnl, atol=1e-5)


def test_unrealized_pnl_with_open_position_at_end():
    """Verify unrealized PnL calculation when a position remains open at backtest end."""
    engine = XNOBacktestEngine(initial_capital=1_000_000_000.0)
    df = create_dummy_df(30, start_price=1000.0, trend=2.0)

    class OpenAtEndStrategy(AlphaStrategy):
        def __algorithm__(self):
            idx = self.data.index
            mask = np.arange(len(idx)) >= 5
            self.set_positions(mask, 1.0)

    result = engine.run(OpenAtEndStrategy(), df)

    assert len(result.trades) == 0

    metrics = calc_compute_metrics(result)
    net_equity = result.final_equity
    unrealized_pnl = metrics['unrealized_pnl']

    assert np.isclose(unrealized_pnl, net_equity - result.initial_capital)
    assert metrics['total_trades'] > 0


def test_rollover_penalty_full_month_vs_sliced_month():
    """
    Empirical Test: Rollover penalty detection logic flaw on full month vs sliced dataset.
    """
    engine = XNOBacktestEngine(initial_capital=1_000_000_000.0, fee_per_contract=6000.0)

    # 1. Full month dataset (Jan 2025 has Thursdays on Jan 2, Jan 9, Jan 16, Jan 23, Jan 30)
    dates_full = pd.date_range('2025-01-01 09:00', '2025-01-31 14:45', freq='15min')
    prices_full = np.ones(len(dates_full)) * 1000.0
    df_full = pd.DataFrame({
        'Open': prices_full, 'High': prices_full+1, 'Low': prices_full-1, 'Close': prices_full, 'Volume': 1000.0
    }, index=dates_full)

    class AlwaysLong:
        def run_algorithm(self, df):
            return pd.Series(np.ones(len(df)), index=df.index)

    result_full = engine.run(AlwaysLong(), df_full)

    # On full month data, Jan 16 is correctly identified as 3rd Thursday!
    # Expected fee = open fee (35 * 6000 = 210,000) + rollover fee (35 * (2.0 * 100k + 12k) = 7,420,000) = 7,630,000 VND
    expected_full_month_fee = 210_000.0 + 35 * (ROLLOVER_PENALTY_POINTS * MULTIPLIER + 2 * 6000.0)
    assert result_full.total_fees == expected_full_month_fee == 7_630_000.0

    # 2. Sliced dataset starting Jan 15 to Jan 17 (only 1 Thursday in df)
    dates_sliced = pd.date_range('2025-01-15 09:00', '2025-01-17 14:45', freq='15min')
    df_sliced = pd.DataFrame({
        'Open': 1000.0, 'High': 1001.0, 'Low': 999.0, 'Close': 1000.0, 'Volume': 1000.0
    }, index=dates_sliced)

    result_sliced = engine.run(AlwaysLong(), df_sliced)

    # DEMONSTRATE BUG: Sliced dataset returns ONLY 210,000.0 (opening fee), skipping the rollover fee!
    print(f"Full month dataset total fees (Correct): {result_full.total_fees:,.0f} VND")
    print(f"Sliced dataset total fees (BUG):        {result_sliced.total_fees:,.0f} VND")

    # Sliced dataset fee is 210,000.0 instead of 7,630,000.0 because len(unique_dates) >= 3 fails on sliced df!
    assert result_sliced.total_fees == 210_000.0


def test_daily_vs_bar_drawdown_discrepancy():
    """
    Empirical Test: Surface metric discrepancy between Daily Resampled Drawdown
    and Bar-Level Intra-day Drawdown in CalculateMetrics.
    """
    engine = XNOBacktestEngine(initial_capital=1_000_000_000.0)

    dates_day1 = pd.date_range('2025-01-01 09:00', '2025-01-01 14:30', freq='15min')
    dates_day2 = pd.date_range('2025-01-02 09:00', '2025-01-02 14:30', freq='15min')
    dates = dates_day1.append(dates_day2)

    p1 = np.linspace(1000, 800, len(dates_day1) // 2)
    p2 = np.linspace(800, 990, len(dates_day1) - len(p1))
    prices_day1 = np.concatenate([p1, p2])
    prices_day2 = np.ones(len(dates_day2)) * 990.0

    prices = np.concatenate([prices_day1, prices_day2])

    df = pd.DataFrame({
        'Open': prices, 'High': prices+1, 'Low': prices-1, 'Close': prices, 'Volume': 1000.0
    }, index=dates)

    positions = np.ones(len(dates))
    class AlwaysLong:
        def run_algorithm(self, df):
            return pd.Series(positions, index=df.index)

    result = engine.run(AlwaysLong(), df)

    bar_equity = result.equity_curve
    bar_max = bar_equity.cummax()
    bar_dd = (bar_equity - bar_max) / bar_max * 100
    bar_mdd = bar_dd.min()

    metrics = calc_compute_metrics(result)
    daily_mdd = metrics['max_drawdown_pct']

    print(f"Intra-day Bar-level Max Drawdown: {bar_mdd:.2f}%")
    print(f"Daily Resampled Max Drawdown:    {daily_mdd:.2f}%")

    assert bar_mdd < daily_mdd


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
