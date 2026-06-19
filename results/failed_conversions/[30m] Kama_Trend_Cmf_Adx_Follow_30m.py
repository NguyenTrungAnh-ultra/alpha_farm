from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.kama_period = int(self.kama_period if 'kama_period' in self.__dict__ else 17)
        self.adx_threshold = float(self.adx_threshold if 'adx_threshold' in self.__dict__ else 30.0)
        kama_period = self.kama_period
        adx_threshold = self.adx_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        kama_trend = self.feat.kama(close, timeperiod=20)
        adx_strength = self.feat.adx(high, low, close, volume, timeperiod=14)
        cmf_volume = self.feat.cmf(volume, timeperiod=5)
        long_setup = (close > kama_trend) & (adx_strength >= 20)
        short_setup = (close < kama_trend) & (adx_strength >= 20)
        exit_long = close <= kama_trend
        exit_short = close >= kama_trend
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)