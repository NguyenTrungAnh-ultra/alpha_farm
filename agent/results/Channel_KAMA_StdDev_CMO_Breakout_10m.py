import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class Channel_KAMA_StdDev_CMO_Breakout(SimpleAlgorithm):
    def __init__(self, kama_period=20, std_period=20, std_mult=2.0, cmo_period=14, cmo_threshold=20.0, sl_points=7.0):
        super().__init__()
        self.kama_period = kama_period
        self.std_period = std_period
        self.std_mult = std_mult
        self.cmo_period = cmo_period
        self.cmo_threshold = cmo_threshold
        self.sl_points = sl_points
        
        self.params = dict(
            kama_period=kama_period,
            std_period=std_period,
            std_mult=std_mult,
            cmo_period=cmo_period,
            cmo_threshold=cmo_threshold,
            sl_points=sl_points
        )

    def __algorithm__(self):
        # 1. Lấy dữ liệu giá
        close = self.data.pv_close

        # 2. Tính indicators (vectorized, qua self.feat)
        kama = self.feat.kama(close, timeperiod=self.kama_period)
        stddev = self.feat.stddev(close, timeperiod=self.std_period, nbdev=1.0)
        cmo = self.feat.cmo(close, timeperiod=self.cmo_period)

        # Tính toán biên trên và biên dưới của kênh
        upper_band = kama + (self.std_mult * stddev)
        lower_band = kama - (self.std_mult * stddev)

        # 3. Tạo điều kiện entry/exit
        long_setup = (close > upper_band) & (cmo > self.cmo_threshold)
        short_setup = (close < lower_band) & (cmo < -self.cmo_threshold)

        exit_long = close < kama
        exit_short = close > kama
        exit_setup = exit_long | exit_short

        # 4. Set positions (EXIT trước, ENTRY sau để override)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)