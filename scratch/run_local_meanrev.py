import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from backtest.metrics import compute_metrics
from xno_sdk.engine import SimpleAlgorithm

class MeanRev_CCI_LinearReg(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        lr_period = int(20)
        slope_limit = float(1.0)
        cci_period = int(14)
        atr_period = int(12)
        sl_mult = float(2.5)

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 2. Tính indicators
        lr_slope = self.feat.linearreg_slope(close, timeperiod=lr_period)
        cci = self.feat.cci(high, low, close, timeperiod=cci_period)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)

        # 3. Điều kiện Entry
        is_sideway = (lr_slope >= -slope_limit) & (lr_slope <= slope_limit)
        cci_cross_up_m100 = (cci > -100) & (cci.shift(1) <= -100)
        long_setup = is_sideway & cci_cross_up_m100
        
        cci_cross_down_100 = (cci < 100) & (cci.shift(1) >= 100)
        short_setup = is_sideway & cci_cross_down_100

        # 4. Theo dõi giá vào lệnh để tính SL
        long_entry_prices = close.where(long_setup).ffill()
        short_entry_prices = close.where(short_setup).ffill()

        # 5. Điều kiện Exit
        exit_long_early = (cci > 0) & (cci.shift(1) <= 0)
        sl_long = close <= (long_entry_prices - sl_mult * atr)
        
        exit_short_early = (cci < 0) & (cci.shift(1) >= 0)
        sl_short = close >= (short_entry_prices + sl_mult * atr)

        exit_setup = exit_long_early | sl_long | exit_short_early | sl_short

        # 6. Đặt lệnh (Exit trước, Entry sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)

df = load_data('30m', start='2020-01-01', end='2025-01-01')
engine = XNOBacktestEngine()
res = engine.run(MeanRev_CCI_LinearReg(), df)
m = compute_metrics(res)

print("Local MeanRev_CCI_LinearReg on Simulate:")
print(f"  Total Trades: {m['total_trades']}")
print(f"  Total Fees: {m['total_fees_vnd']:,.2f}")
print(f"  Final Equity: {m['net_equity']:,.2f}")
print(f"  CAGR: {m['cagr_pct']:.4f}%")
print(f"  Sharpe Ratio: {m['sharpe_ratio']:.4f}")
print(f"  Max Drawdown: {m['max_drawdown_pct']:.4f}%")
print(f"  Profit Factor: {m['profit_factor']:.4f}")
