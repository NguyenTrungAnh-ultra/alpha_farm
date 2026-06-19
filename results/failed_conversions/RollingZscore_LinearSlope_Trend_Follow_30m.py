from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 0.0)
        self.zscore_pullback = int(self.zscore_pullback if 'zscore_pullback' in self.__dict__ else 0)
        slope_threshold = self.slope_threshold
        zscore_pullback = self.zscore_pullback
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        linearregslope = self.feat.linearreg_slope(close, timeperiod=20)
        rollingzscore = self.feat.rolling_zscore(close, rolling_mean=True)
        long_setup = (linearreg_slope > 0) & (rolling_zscore < -1)
        short_setup = (linearreg_slope < 0) & (rolling_zscore > +1)
        exit_long = ~(linearreg_slope >= 0) | (rolling_zscore > +2)
        exit_short = (linearreg_slope >= 0) | (rolling_zscore < -2)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)