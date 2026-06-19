from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.zscore_threshold_long = float(self.zscore_threshold_long if 'zscore_threshold_long' in self.__dict__ else -2.15)
        self.adx_filter_limit = int(self.adx_filter_limit if 'adx_filter_limit' in self.__dict__ else 30)
        zscore_threshold_long = self.zscore_threshold_long
        adx_filter_limit = self.adx_filter_limit
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        rolling_zscore = self.feat.rolling_zscore(close, timeperiod=20)
        sma_mean = self.feat.sma(close, timeperiod=14)
        cmf_flow = self.feat.cmf(high, low, open_price, volume)
        adx_strength = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (rolling_zscore < -2.0) & (cmf_flow > 0.5) & (adx_strength < 30)
        short_setup = (rolling_zscore > 2.0) & (cmf_flow < -0.5) & (adx_strength < 30)
        exit_long = (self.op.abs(rolling_zscore) < 1.0) | (close >= sma_mean + rolling_std(sma_mean, timeperiod=14))
        exit_short = (self.op.abs(rolling_zscore) < 1.0) | (close <= sma_mean - rolling_std(sma_mean, timeperiod=14))
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)