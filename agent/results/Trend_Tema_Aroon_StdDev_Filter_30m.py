import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class Trend_Tema_Aroon_StdDev_Filter(SimpleAlgorithm):
    def __init__(self, tema_period=30, aroon_period=20, stddev_period=20):
        super().__init__()
        self.tema_period = tema_period
        self.aroon_period = aroon_period
        self.stddev_period = stddev_period
        self.params = dict(
            tema_period=tema_period,
            aroon_period=aroon_period,
            stddev_period=stddev_period
        )

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 1. Indicators
        tema = self.feat.tema(close, timeperiod=self.tema_period)
        aroon_down, aroon_up = self.feat.aroon(high, low, timeperiod=self.aroon_period)
        
        # Volatility filter
        stddev = self.feat.stddev(close, timeperiod=self.stddev_period)
        stddev_ma = self.feat.sma(stddev, timeperiod=self.stddev_period)
        vol_filter = stddev > stddev_ma

        # 2. Logic điều kiện
        long_setup = (aroon_up > 70) & (aroon_down < 30) & (close > tema) & vol_filter
        short_setup = (aroon_down > 70) & (aroon_up < 30) & (close < tema) & vol_filter
        
        # 3. Exit logic
        # (1) Aroon cắt xuống dưới 50, (2) Giá cắt ngược TEMA
        # Lỗ 15 điểm là quản lý rủi ro mặc định (Fixed Stop Loss)
        exit_long = (aroon_up < 50) | (close < tema)
        exit_short = (aroon_down < 50) | (close > tema)
        exit_setup = exit_long | exit_short

        # 4. Set positions (EXIT trước, ENTRY sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)