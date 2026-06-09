import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class Pattern_Marubozu_TEMA_RSI_Breakout(SimpleAlgorithm):
    def __init__(self, tema_period=40, rsi_period=14, rsi_upper_limit=70.0, rsi_lower_limit=30.0, sl_points=15.0):
        super().__init__()
        self.tema_period = tema_period
        self.rsi_period = rsi_period
        self.rsi_upper_limit = rsi_upper_limit
        self.rsi_lower_limit = rsi_lower_limit
        self.sl_points = sl_points
        
        self.params = dict(
            tema_period=tema_period,
            rsi_period=rsi_period,
            rsi_upper_limit=rsi_upper_limit,
            rsi_lower_limit=rsi_lower_limit,
            sl_points=sl_points
        )

    def __algorithm__(self):
        # 1. Lấy dữ liệu giá
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close

        # 2. Tính indicators (vectorized, qua self.feat)
        marubozu = self.feat.cdlmarubozu(open_, high, low, close)
        tema = self.feat.tema(close, timeperiod=self.tema_period)
        rsi = self.feat.rsi(close, timeperiod=self.rsi_period)

        # 3. Tạo điều kiện entry/exit
        long_setup = (marubozu == 100) & (close > tema) & (rsi < self.rsi_upper_limit)
        short_setup = (marubozu == -100) & (close < tema) & (rsi > self.rsi_lower_limit)

        exit_long = (close < tema) | (rsi > 85)
        exit_short = (close > tema) | (rsi < 15)
        exit_setup = exit_long | exit_short

        # 4. Set positions (EXIT trước, ENTRY sau để override)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)