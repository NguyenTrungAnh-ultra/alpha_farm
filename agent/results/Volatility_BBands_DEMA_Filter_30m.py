import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class Volatility_BBands_DEMA_Filter(SimpleAlgorithm):
    def __init__(self, bbands_period=20, bbands_stddev=2.0, dema_period=40, atr_period=14, sl_mult=2.0, tp_points=25):
        super().__init__()
        self.bbands_period = bbands_period
        self.bbands_stddev = bbands_stddev
        self.dema_period = dema_period
        self.atr_period = atr_period
        self.sl_mult = sl_mult
        self.tp_points = tp_points
        
        self.params = dict(
            bbands_period=bbands_period,
            bbands_stddev=bbands_stddev,
            dema_period=dema_period,
            atr_period=atr_period,
            sl_mult=sl_mult,
            tp_points=tp_points
        )

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 1. Tính indicators
        upper, middle, lower = self.feat.bbands(close, timeperiod=self.bbands_period, nbdevup=self.bbands_stddev, nbdevdn=self.bbands_stddev)
        dema = self.feat.dema(close, timeperiod=self.dema_period)
        atr = self.feat.atr(high, low, close, timeperiod=self.atr_period)

        # Logic Squeeze: Khoảng cách giữa các dải đang thu hẹp (độ rộng dải nhỏ hơn mức trung bình 20 kỳ)
        bandwidth = (upper - lower) / middle
        is_squeeze = bandwidth < bandwidth.rolling(window=20).mean()

        # 2. Điều kiện Entry
        # Entry Long: Breakout upper, giá > DEMA, đang trong trạng thái squeeze
        long_setup = (close > upper) & (close > dema) & is_squeeze
        
        # Entry Short: Breakout lower, giá < DEMA, đang trong trạng thái squeeze
        short_setup = (close < lower) & (close < dema) & is_squeeze

        # 3. Theo dõi giá vào lệnh để tính TP/SL
        long_entry_prices = pd.Series(np.where(long_setup, close, np.nan), index=close.index).ffill()
        short_entry_prices = pd.Series(np.where(short_setup, close, np.nan), index=close.index).ffill()

        # 4. Điều kiện Exit
        # Thoát lệnh: chạm TP, SL hoặc giá cắt ngược qua Middle Band
        tp_long = close >= (long_entry_prices + self.tp_points)
        sl_long = close <= (long_entry_prices - self.sl_mult * atr)
        early_exit_long = close < middle
        
        tp_short = close <= (short_entry_prices - self.tp_points)
        sl_short = close >= (short_entry_prices + self.sl_mult * atr)
        early_exit_short = close > middle

        exit_setup = tp_long | sl_long | early_exit_long | tp_short | sl_short | early_exit_short

        # 5. Đặt lệnh (Exit trước, Entry sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)