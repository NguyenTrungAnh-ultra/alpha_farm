from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.z_score_threshold = float(self.z_score_threshold if 'z_score_threshold' in self.__dict__ else 1.75)
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 22)
        z_score_threshold = self.z_score_threshold
        slope_period = self.slope_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        rolling_zscore = self.feat.rolling_zscore(close, timeperiod=30)
        linearreg_slope = self.feat.linearreg_slope(close, timeperiod=20)
        long_setup = (rolling_zscore > 1.5) & (slope > 0)
        short_setup = close != close
        exit_long = close != close
        exit_short = (close < self.feat.sma(close)) | (rolling_zscore < -1.0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)