"""Trade reconstruction and rollover-mask cache of AlphaBacktestEngine (synthetic data only)."""
import numpy as np
import pandas as pd
import pytest

from core_engine.BacktestEngine import (
    AlphaBacktestEngine, _compute_rollover_mask, _rollover_mask,
)
from utilities.AppConfig import (
    FEE_PER_CONTRACT_PER_SIDE, INITIAL_CAPITAL, MAINTENANCE_MARGIN_RATE, MARGIN_RATE, MULTIPLIER,
)


class _Fixed:
    def __init__(self, positions):
        self.positions = positions

    def run_algorithm(self, df):
        return self.positions.copy()


def _frame(closes, start='2024-01-02 09:00'):
    idx = pd.date_range(start, periods=len(closes), freq='h')
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({'Open': c, 'High': c, 'Low': c, 'Close': c, 'Volume': 1.0}, index=idx)


def test_rollover_mask_cache_matches_fresh_mask_for_indices_sharing_endpoints():
    # Third Thursdays of Jan/Feb/Mar 2024: 18th, 15th, 21st.
    a = pd.date_range('2024-01-02 09:00', '2024-03-29 15:00', freq='h')
    # `b`: same length and endpoints, but the January expiry day's bars moved one day later.
    on_expiry = a.normalize() == pd.Timestamp('2024-01-18')
    b = a.where(~on_expiry, a + pd.Timedelta(days=1)).sort_values()
    # `c`: same length and endpoints, one interior bar shifted by a minute.
    c = a.delete(100).insert(100, a[100] + pd.Timedelta(minutes=1))
    assert b[0] == a[0] and b[-1] == a[-1] and len(b) == len(a)
    assert c[0] == a[0] and c[-1] == a[-1] and len(c) == len(a)

    for index in (a, c, a, b, c, a):
        np.testing.assert_array_equal(_rollover_mask(index), _compute_rollover_mask(index))
    assert not np.array_equal(_rollover_mask(a), _rollover_mask(b))
    assert _rollover_mask(a).sum() == 3
    assert not _rollover_mask(a).flags.writeable


def test_trade_reconstruction_with_reversal():
    closes = [1000, 1010, 1020, 1030, 1010, 1000, 1000, 1000]
    df = _frame(closes)
    # Signals execute one bar later: long on bars 1-2, short on bars 3-4, flat after.
    pos = pd.Series([1, 1, -1, -1, 0, 0, 0, 0], index=df.index, dtype=float)
    res = AlphaBacktestEngine().run(_Fixed(pos), df)

    n = round(INITIAL_CAPITAL / (1010 * MULTIPLIER * MARGIN_RATE))
    fee = FEE_PER_CONTRACT_PER_SIDE
    assert len(res.trades) == 2
    long_trade, short_trade = res.trades

    assert (long_trade.entry_bar, long_trade.exit_bar) == (1, 3)
    assert long_trade.entry_time == df.index[1] and long_trade.exit_time == df.index[3]
    assert isinstance(long_trade.entry_time, pd.Timestamp) and isinstance(long_trade.exit_time, pd.Timestamp)
    assert long_trade.direction == 1.0 and long_trade.contracts == n
    assert long_trade.entry_price == 1010 and long_trade.exit_price == 1030
    assert long_trade.gross_pnl == pytest.approx(20 * n * MULTIPLIER)
    assert long_trade.fee == pytest.approx(2 * n * fee)
    assert long_trade.net_pnl == pytest.approx(20 * n * MULTIPLIER - 2 * n * fee)

    assert (short_trade.entry_bar, short_trade.exit_bar) == (3, 5)
    assert short_trade.entry_time == df.index[3] and short_trade.exit_time == df.index[5]
    assert short_trade.direction == -1.0 and short_trade.contracts == n
    assert short_trade.entry_price == 1030 and short_trade.exit_price == 1000
    assert short_trade.gross_pnl == pytest.approx(30 * n * MULTIPLIER)
    assert short_trade.net_pnl == pytest.approx(30 * n * MULTIPLIER - 2 * n * fee)

    assert res.total_trades == 3  # open, reversal, close
    assert res.total_fees == pytest.approx(4 * n * fee)
    assert res.final_equity == pytest.approx(INITIAL_CAPITAL + long_trade.net_pnl + short_trade.net_pnl)


def test_trade_reconstruction_margin_call():
    closes = [1000, 1000, 950, 900, 900, 900]
    df = _frame(closes)
    pos = pd.Series([4, 4, 4, 4, 4, 4], index=df.index, dtype=float)
    res = AlphaBacktestEngine().run(_Fixed(pos), df)

    threshold = INITIAL_CAPITAL * (1 - (MARGIN_RATE - MAINTENANCE_MARGIN_RATE) / MARGIN_RATE)
    n = round(4 * INITIAL_CAPITAL / (1000 * MULTIPLIER * MARGIN_RATE))
    assert len(res.trades) == 1
    trade = res.trades[0]
    # Entry at bar 1 (signal of bar 0 executes at bar 1); the 50-point drop on bar 2 breaches.
    assert (trade.entry_bar, trade.exit_bar) == (1, 2)
    assert trade.contracts == n and trade.direction == 1.0
    assert trade.net_pnl == pytest.approx(threshold - INITIAL_CAPITAL)
    assert res.final_equity == pytest.approx(threshold)
    np.testing.assert_allclose(res.equity_curve.iloc[2:].to_numpy(), threshold)
    assert (res.positions.iloc[2:] == 0.0).all()
