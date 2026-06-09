import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class Trend_T3_UltOsc_VolumeOsc(SimpleAlgorithm):
    def __init__(self, t3_period=20, ultosc_short=7, ultosc_medium=14, adosc_fast=5, adosc_slow=20):
        super().__init__()
        self.t3_period = t3_period
        self.ultosc_short = ultosc_short
        self.ultosc_medium = ultosc_medium
        self.adosc_fast = adosc_fast
        self.adosc_slow = adosc_slow
        self.params = dict(
            t3_period=t3_period,
            ultosc_short=ultosc_short,
            ultosc_medium=ultosc_medium,
            adosc_fast=adosc_fast,
            adosc_slow=adosc_slow
        )

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume

        # 1. Tính toán indicators
        t3 = self.feat.t3(close, timeperiod=self.t3_period)
        ultosc = self.feat.ultosc(high, low, close, timeperiod1=self.ultosc_short, timeperiod2=self.ultosc_medium, timeperiod3=28)
        adosc = self.feat.adosc(high, low, close, volume, fastperiod=self.adosc_fast, slowperiod=self.adosc_slow)
        
        # 2. Logic Exit (Thoát trước)
        # Giá cắt ngược T3
        exit_t3 = ((close < t3) & (close.shift(1) >= t3.shift(1))) | ((close > t3) & (close.shift(1) <= t3.shift(1)))
        # UltOsc quá mua/quá bán
        exit_ult = (ultosc > 70) | (ultosc < 30)
        
        exit_setup = exit_t3 | exit_ult

        # 3. Logic Entry
        # UltOsc cắt 50
        ultosc_cross_up = (ultosc > 50) & (ultosc.shift(1) <= 50)
        ultosc_cross_down = (ultosc < 50) & (ultosc.shift(1) >= 50)
        
        long_setup = (close > t3) & ultosc_cross_up & (adosc > 0)
        short_setup = (close < t3) & ultosc_cross_down & (adosc < 0)

        # 4. Set positions (EXIT trước, ENTRY sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)