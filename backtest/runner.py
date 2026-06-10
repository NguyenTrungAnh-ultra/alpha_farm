"""
XNOQuant Engine — Runner
=========================
CLI để chạy backtest và hiển thị kết quả.
"""

import sys
import os

# Thêm project root vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.engine import XNOBacktestEngine, load_data
from xno_sdk.engine import SimpleAlgorithm
from backtest.metrics import print_report, compute_metrics, validate_metrics
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("xno_sdk.runner")


# =============================================================================
# CÁC STRATEGY MẪU (Copy từ XNOQuant, chỉ đổi import)
# =============================================================================

class BuyAndHold(SimpleAlgorithm):
    """Test 1: Buy and Hold, position=1.0"""
    def __algorithm__(self):
        close = self.data.pv_close
        always_true = close > 0
        self.set_positions(always_true, position=1.0)


class BuyAndHoldHalf(SimpleAlgorithm):
    """Test 3: Buy and Hold, position=0.5"""
    def __algorithm__(self):
        close = self.data.pv_close
        always_true = close > 0
        self.set_positions(always_true, position=0.5)


class SMA_StopAndReverse(SimpleAlgorithm):
    """Test 6: SMA10 Stop & Reverse (luôn có vị thế, long hoặc short)"""
    def __algorithm__(self):
        close = self.data.pv_close
        sma = self.feat.sma(close, timeperiod=10)
        long_zone = close > sma
        short_zone = ~long_zone
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)


class SMA_LongFlat(SimpleAlgorithm):
    """Test 7: SMA10 Long/Flat (chỉ long hoặc flat)"""
    def __algorithm__(self):
        close = self.data.pv_close
        sma = self.feat.sma(close, timeperiod=10)
        long_zone = close > sma
        flat_zone = ~long_zone
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)


class SMA_Channel(SimpleAlgorithm):
    """Strategy gốc từ nền tảng (class cuối trong strategies.py)"""
    def __algorithm__(self):
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close

        sma_high = self.feat.sma(high, timeperiod=10).fillna(99999)
        sma_low = self.feat.sma(low, timeperiod=10).fillna(0)
        sma_close = self.feat.sma(close, timeperiod=10).fillna(0)

        long_setup = close > sma_high
        short_setup = close < sma_low
        exit_long = close < sma_close
        exit_short = close > sma_close
        exit_setup = exit_long | exit_short

        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)


class SMA_5_20_SAR(SimpleAlgorithm):
    """Test 2: SMA 5/20 Stop & Reverse"""
    def __algorithm__(self):
        close = self.data.pv_close
        sma5 = self.feat.sma(close, timeperiod=5)
        sma20 = self.feat.sma(close, timeperiod=20)
        long_zone = sma5 > sma20
        short_zone = sma5 < sma20
        flat_zone = ~long_zone & ~short_zone
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)


class SMA_3_1000_LF(SimpleAlgorithm):
    """Test 8: SMA 3/1000 Long/Flat"""
    def __algorithm__(self):
        close = self.data.pv_close
        sma_fast = self.feat.sma(close, timeperiod=3)
        sma_slow = self.feat.sma(close, timeperiod=1000)
        long_zone = sma_fast > sma_slow
        flat_zone = ~long_zone
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)


# =============================================================================
# MAIN
# =============================================================================

from strategies.alpha_42 import CustomStrategy as Alpha42

STRATEGIES = {
    'buy_hold': BuyAndHold,
    'buy_hold_half': BuyAndHoldHalf,
    'sma10_sar': SMA_StopAndReverse,
    'sma10_lf': SMA_LongFlat,
    'sma_channel': SMA_Channel,
    'sma5_20': SMA_5_20_SAR,
    'sma3_1000': SMA_3_1000_LF,
    'alpha_42': Alpha42,
}


def run_verification():
    """Chạy tất cả test cases và so sánh với XNOQuant."""

    print("=" * 75)
    print("  VERIFICATION: So sánh Local Engine vs XNOQuant")
    print("=" * 75)

    # XNO reference values
    xno_ref = {
        'buy_hold': {
            'unrealized_pnl': 1_872_160_000,
            'total_trades': 1,
            'total_fees_pct': 0.02,
            'initial_capital': 999_760_000,
        },
        'buy_hold_half': {
            'unrealized_pnl': 936_080_000,
            'total_trades': 1,
            'total_fees_pct': 0.01,
            'initial_capital': 999_880_000,
        },
        'sma10_sar': {
            'total_trades': 4859,
            'total_fees_pct': 233.26,
            'cumulative_return': 645.53,
        },
        'sma10_lf': {
            'total_trades': 4858,
            'total_fees_pct': 116.59,
            'cumulative_return': 409.77,
            'net_equity': 5_243_280_000,
        },
        'sma_channel': {
            'total_trades': 5502,
            'cumulative_return': 463.99,
        },
        'sma5_20': {
            'total_trades': 1846,
            'total_fees_pct': 88.58,
            'cumulative_return': 596.89,
        },
        'sma3_1000': {
            'total_trades': 179,
            'total_fees_pct': 4.30,
            'cumulative_return': 275.02,
            'net_equity': 3_750_240_000,
        },
    }

    engine = XNOBacktestEngine()
    df = load_data('10m')

    for name, StrategyClass in STRATEGIES.items():
        print(f"\n{'-' * 75}")
        print(f"  Strategy: {name}")
        print(f"{'-' * 75}")

        strategy = StrategyClass()
        result = engine.run(strategy, df)
        m = compute_metrics(result)

        ref = xno_ref.get(name, {})

        print(f"  {'Metric':<25} {'Local':>18} {'XNO':>18} {'Match':>8}")
        print(f"  {'-' * 69}")

        if 'total_trades' in ref:
            match = 'OK' if m['total_trades'] == ref['total_trades'] else 'ERR'
            print(f"  {'Total Trades':<25} {m['total_trades']:>18} {ref['total_trades']:>18} {match:>8}")

        if 'total_fees_pct' in ref:
            err = abs(m['total_fees_pct'] - ref['total_fees_pct'])
            match = 'OK' if err < 1.0 else f'D{err:.1f}'
            print(f"  {'Total Fees %':<25} {m['total_fees_pct']:>17.2f}% {ref['total_fees_pct']:>17.2f}% {match:>8}")

        if 'cumulative_return' in ref:
            err = abs(m['cumulative_return_pct'] - ref['cumulative_return'])
            match = 'OK' if err < 5.0 else f'D{err:.1f}'
            print(f"  {'Cumulative Return':<25} {m['cumulative_return_pct']:>17.2f}% {ref['cumulative_return']:>17.2f}% {match:>8}")

        if 'unrealized_pnl' in ref:
            err = abs(m['unrealized_pnl'] - ref['unrealized_pnl'])
            match = 'OK' if err < 10_000_000 else f'D{err:,.0f}'
            print(f"  {'Unrealized PnL':<25} {m['unrealized_pnl']:>18,.0f} {ref['unrealized_pnl']:>18,.0f} {match:>8}")

        if 'net_equity' in ref:
            err = abs(m['net_equity'] - ref['net_equity'])
            match = 'OK' if err < 50_000_000 else f'D{err:,.0f}'
            print(f"  {'Net Equity':<25} {m['net_equity']:>18,.0f} {ref['net_equity']:>18,.0f} {match:>8}")

        if 'initial_capital' in ref:
            err = abs(m['initial_capital'] - ref['initial_capital'])
            match = 'OK' if err < 10_000 else f'D{err:,.0f}'
            print(f"  {'Initial Capital':<25} {m['initial_capital']:>18,.0f} {ref['initial_capital']:>18,.0f} {match:>8}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='XNOQuant Local Backtest Engine')
    parser.add_argument('--strategy', '-s', type=str, default='buy_hold',
                        choices=list(STRATEGIES.keys()),
                        help='Strategy to run')
    parser.add_argument('--timeframe', '-t', type=str, default='10m',
                        help='Timeframe (1m, 3m, 5m, 10m, 15m, 30m, 60m)')
    parser.add_argument('--verify', '-v', action='store_true',
                        help='Run verification against XNO reference values')

    args = parser.parse_args()

    if args.verify:
        run_verification()
    else:
        print(f"Loading {args.timeframe} data...")
        df = load_data(args.timeframe)
        print(f"Loaded {len(df)} bars ({df.index[0]} to {df.index[-1]})")
        strategy = STRATEGIES[args.strategy]()
        engine = XNOBacktestEngine()

        print(f"Running {args.strategy}...")
        result = engine.run(strategy, df)
        metrics = compute_metrics(result)
        print_report(result)
        
        try:
            validate_metrics(metrics)
        except ValueError as e:
            logger.warning(f"Metrics validation failed: {e}")
