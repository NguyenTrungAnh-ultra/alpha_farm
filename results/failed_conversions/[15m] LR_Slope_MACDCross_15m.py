from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else -2.5)
        self.macd_threshold = int(self.macd_threshold if 'macd_threshold' in self.__dict__ else 11)
        slope_threshold = self.slope_threshold
        macd_threshold = self.macd_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope_value = self.feat.linearreg_slope(close, timeperiod=20)
        macd_hist = self.feat[0](close, timeperiod=14)
        long_setup = (slope_val > 5.0) & (macd_hist > 0)
        short_setup = (slope_val < -5.0) & (macd_hist < 0)
        exit_long = (macd_hist <= 0) | (close < self.feat.linearreg(close, timeperiod=20))
        exit_short = (macd_hist >= 0) | (close > self.feat.linearreg(close, timeperiod=20))
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)