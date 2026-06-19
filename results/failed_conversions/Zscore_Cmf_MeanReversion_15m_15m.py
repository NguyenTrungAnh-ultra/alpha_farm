from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.zscore_threshold = float(self.zscore_threshold if 'zscore_threshold' in self.__dict__ else 2.25)
        self.cmf_min_level = float(self.cmf_min_level if 'cmf_min_level' in self.__dict__ else 0.1)
        zscore_threshold = self.zscore_threshold
        cmf_min_level = self.cmf_min_level
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        rolling_zscore = self.feat.rolling_zscore(close, timeperiod=20)
        cmf = self.feat.cmf(volume)
        long_setup = (rolling_zscore < -1.5) & (cmf > 0)
        short_setup = (rolling_zscore > 1.5) & (cmf < 0)
        exit_long = close >= rolling_mean(close, timeperiod=20)
        exit_short = close <= rolling_mean(close, timeperiod=20)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)