import talib
import numpy as np
import pandas as pd
from backtest.strategy import SimpleAlgorithm

class Session_PriceChannel_ROC_Filter(SimpleAlgorithm):
    def __init__(self, channel_period=4, roc_period=14, atr_filter=1.5):
        super().__init__()
        self.channel_period = channel_period
        self.roc_period = roc_period
        self.atr_filter = atr_filter
        self.params = dict(
            channel_period=channel_period,
            roc_period=roc_period,
            atr_filter=atr_filter
        )

    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        
        # 1. Tính toán vùng giá phiên mở cửa (4 thanh đầu tiên)
        # Giả định dữ liệu index là datetime, xác định giờ mở cửa (thường là 9:00 hoặc 9:15 tại VN)
        # Xử lý vector để lấy Max/Min trong khoảng thời gian nhất định (4 bars đầu)
        session_high = high.iloc[:self.channel_period].max()
        session_low = low.iloc[:self.channel_period].min()
        
        # 2. Indicators
        roc = self.feat.roc(close, timeperiod=self.roc_period)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        
        # 3. Điều kiện Entry
        # Tránh quá mở rộng: giá hiện tại không nên quá xa so với dải ATR
        not_extended = (abs(close - close.rolling(self.roc_period).mean()) < (self.atr_filter * atr))
        
        long_setup = (close > session_high) & (roc > 0) & not_extended
        short_setup = (close < session_low) & (roc < 0) & not_extended
        
        # 4. Điều kiện Exit
        # ROC đảo chiều > 5% hoặc < -5%, hoặc giá quay lại trong vùng session
        exit_roc = (roc > 5.0) | (roc < -5.0)
        exit_reentry = (close < session_high) & (close > session_low)
        exit_setup = exit_roc | exit_reentry
        
        # Set positions
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)