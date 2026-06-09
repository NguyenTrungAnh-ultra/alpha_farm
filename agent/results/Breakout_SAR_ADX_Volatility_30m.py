import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class Breakout_SAR_ADX_Volatility(SimpleAlgorithm):
    def __init__(self, sar_accel=0.02, sar_max=0.2, adx_period=14, adx_threshold=25.0, 
                 atr_period=14, vol_factor=1.0, sl_mult=2.0, tp_mult=3.0):
        super().__init__()
        self.sar_accel = sar_accel
        self.sar_max = sar_max
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.atr_period = atr_period
        self.vol_factor = vol_factor
        self.sl_mult = sl_mult
        self.tp_mult = tp_mult
        
        self.params = dict(
            sar_accel=sar_accel,
            sar_max=sar_max,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            atr_period=atr_period,
            vol_factor=vol_factor,
            sl_mult=sl_mult,
            tp_mult=tp_mult
        )

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 1. Tính indicators
        sar = self.feat.sar(high, low, acceleration=self.sar_accel, maximum=self.sar_max)
        adx = self.feat.adx(high, low, close, timeperiod=self.adx_period)
        trange = self.feat.trange(high, low, close)
        atr = self.feat.atr(high, low, close, timeperiod=self.atr_period)

        # 2. Điều kiện Entry
        # Breakout SAR
        sar_cross_up = (close > sar) & (close.shift(1) <= sar.shift(1))
        sar_cross_down = (close < sar) & (close.shift(1) >= sar.shift(1))
        
        # Volatility filter
        vol_confirm = trange > (atr * self.vol_factor)
        
        long_setup = sar_cross_up & (adx > self.adx_threshold) & vol_confirm
        short_setup = sar_cross_down & (adx > self.adx_threshold) & vol_confirm

        # 3. Theo dõi giá vào lệnh để tính TP/SL
        long_entry_prices = pd.Series(np.where(long_setup, close, np.nan), index=close.index).ffill()
        short_entry_prices = pd.Series(np.where(short_setup, close, np.nan), index=close.index).ffill()

        # 4. Điều kiện Exit
        # Thoát khi: TP/SL, hoặc giá cắt ngược SAR
        tp_long = close >= (long_entry_prices + self.tp_mult * atr)
        sl_long = close <= (long_entry_prices - self.sl_mult * atr)
        early_exit_long = close < sar
        
        tp_short = close <= (short_entry_prices - self.tp_mult * atr)
        sl_short = close >= (short_entry_prices + self.sl_mult * atr)
        early_exit_short = close > sar

        exit_setup = tp_long | sl_long | early_exit_long | tp_short | sl_short | early_exit_short

        # 5. Set positions (Exit trước, Entry sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)