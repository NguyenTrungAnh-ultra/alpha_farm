import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class MeanRev_CCI_LinearReg(SimpleAlgorithm):
    def __init__(self, lr_period=30, slope_limit=2.0, cci_period=20, atr_period=14, sl_mult=2.0):
        super().__init__()
        self.lr_period = lr_period
        self.slope_limit = slope_limit
        self.cci_period = cci_period
        self.atr_period = atr_period
        self.sl_mult = sl_mult
        
        self.params = dict(
            lr_period=lr_period,
            slope_limit=slope_limit,
            cci_period=cci_period,
            atr_period=atr_period,
            sl_mult=sl_mult
        )

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 1. Tính indicators
        lr_slope = self.feat.linearreg_slope(close, timeperiod=self.lr_period)
        cci = self.feat.cci(high, low, close, timeperiod=self.cci_period)
        atr = self.feat.atr(high, low, close, timeperiod=self.atr_period)

        # 2. Điều kiện Entry
        # Sideway filter
        is_sideway = (lr_slope >= -self.slope_limit) & (lr_slope <= self.slope_limit)
        
        # CCI cắt lên mức -100
        cci_cross_up_m100 = (cci > -100) & (cci.shift(1) <= -100)
        long_setup = is_sideway & cci_cross_up_m100
        
        # CCI cắt xuống mức 100
        cci_cross_down_100 = (cci < 100) & (cci.shift(1) >= 100)
        short_setup = is_sideway & cci_cross_down_100

        # 3. Theo dõi giá vào lệnh để tính SL
        long_entry_prices = pd.Series(np.where(long_setup, close, np.nan), index=close.index).ffill()
        short_entry_prices = pd.Series(np.where(short_setup, close, np.nan), index=close.index).ffill()

        # 4. Điều kiện Exit
        # Thoát Long khi hồi về 0 hoặc chạm SL
        exit_long_early = (cci > 0) & (cci.shift(1) <= 0)
        sl_long = close <= (long_entry_prices - self.sl_mult * atr)
        
        # Thoát Short khi hồi về 0 hoặc chạm SL
        exit_short_early = (cci < 0) & (cci.shift(1) >= 0)
        sl_short = close >= (short_entry_prices + self.sl_mult * atr)

        # Tổng hợp Exit
        exit_setup = exit_long_early | sl_long | exit_short_early | sl_short

        # 5. Đặt lệnh (Exit trước, Entry sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)