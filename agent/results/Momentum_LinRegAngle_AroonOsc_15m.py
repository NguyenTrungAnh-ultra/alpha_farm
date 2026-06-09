import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class Momentum_LinRegAngle_AroonOsc(SimpleAlgorithm):
    def __init__(self, angle_period=14, angle_threshold=20.0, aroon_period=14, aroon_threshold=50, atr_period=14, sl_mult=2.0, tp_mult=4.0):
        super().__init__()
        self.angle_period = angle_period
        self.angle_threshold = angle_threshold
        self.aroon_period = aroon_period
        self.aroon_threshold = aroon_threshold
        self.atr_period = atr_period
        self.sl_mult = sl_mult
        self.tp_mult = tp_mult
        
        self.params = dict(
            angle_period=self.angle_period,
            angle_threshold=self.angle_threshold,
            aroon_period=self.aroon_period,
            aroon_threshold=self.aroon_threshold,
            atr_period=self.atr_period,
            sl_mult=self.sl_mult,
            tp_mult=self.tp_mult
        )

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 1. Tính indicators
        angle = self.feat.linearreg_angle(close, timeperiod=self.angle_period)
        aroonosc = self.feat.aroonosc(high, low, timeperiod=self.aroon_period)
        atr = self.feat.atr(high, low, close, timeperiod=self.atr_period)

        # 2. Tạo điều kiện entry
        long_setup = (angle > self.angle_threshold) & (aroonosc > self.aroon_threshold)
        short_setup = (angle < -self.angle_threshold) & (aroonosc < -self.aroon_threshold)

        # 3. Theo dõi giá vào lệnh để tính TP/SL
        long_entry_prices = pd.Series(np.where(long_setup, close, np.nan), index=close.index).ffill()
        short_entry_prices = pd.Series(np.where(short_setup, close, np.nan), index=close.index).ffill()

        # 4. Điều kiện exit
        # Exit Long: TP, SL, hoặc AROONOSC cắt xuống dưới 0
        exit_long_tp = close >= (long_entry_prices + self.tp_mult * atr)
        exit_long_sl = close <= (long_entry_prices - self.sl_mult * atr)
        exit_long_early = (aroonosc < 0) & (aroonosc.shift(1) >= 0)
        
        # Exit Short: TP, SL, hoặc AROONOSC cắt lên trên 0
        exit_short_tp = close <= (short_entry_prices - self.tp_mult * atr)
        exit_short_sl = close >= (short_entry_prices + self.sl_mult * atr)
        exit_short_early = (aroonosc > 0) & (aroonosc.shift(1) <= 0)

        # Tổng hợp tín hiệu thoát
        exit_setup = exit_long_tp | exit_long_sl | exit_long_early | exit_short_tp | exit_short_sl | exit_short_early

        # 5. Set positions (EXIT trước, ENTRY sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)