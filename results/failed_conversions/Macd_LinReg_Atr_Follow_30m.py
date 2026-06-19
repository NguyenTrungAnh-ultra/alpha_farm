from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.linearreg_period = int(self.linearreg_period if 'linearreg_period' in self.__dict__ else 22)
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 13.5)
        linearreg_period = self.linearreg_period
        slope_threshold = self.slope_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        macd_hist = self.feat.macd(close, timeperiod=12)[0]
        linearreg_slope = self.feat.linearreg_slope(high, low, close, timeperiod=20)
        atr_filter = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (macd_hist > 0) & (macd_hist[1] <= 0) & (linearreg_slope > slope_threshold) & (atr_filter < atr_max)
        short_setup = (macd_hist < 0) & (macd_hist[1] >= 0) & (linearreg_slope < -slope_threshold)
        exit_long = (close <= LinearReg_line) | (macd_hist <= 0)
        exit_short = (close >= LinearReg_line) | (macd_hist > 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)