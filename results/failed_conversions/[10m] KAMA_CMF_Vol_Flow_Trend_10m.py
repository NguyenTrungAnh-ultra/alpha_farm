from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.kama_period = int(self.kama_period if 'kama_period' in self.__dict__ else 20)
        self.cmf_threshold_long = float(self.cmf_threshold_long if 'cmf_threshold_long' in self.__dict__ else 0.15)
        kama_period = self.kama_period
        cmf_threshold_long = self.cmf_threshold_long
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        kama_fast = self.feat.kama(close, timeperiod=10)
        cmf_flow = self.feat.cmf(timeperiod=20)
        long_setup = (close > kama_fast) & (cmf_flow > 0.5)
        short_setup = (close < kama_fast) & (cmf_flow < -0.5)
        exit_long = close <= kama_fast
        exit_short = close >= kama_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)