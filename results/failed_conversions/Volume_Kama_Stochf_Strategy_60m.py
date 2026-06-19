from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.kama_period = int(self.kama_period if 'kama_period' in self.__dict__ else 17)
        self.stoch_length = int(self.stoch_length if 'stoch_length' in self.__dict__ else 19)
        self.cmf_threshold_long = float(self.cmf_threshold_long if 'cmf_threshold_long' in self.__dict__ else -0.1)
        kama_period = self.kama_period
        stoch_length = self.stoch_length
        cmf_threshold_long = self.cmf_threshold_long
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        kama_fast = self.feat.kama(close, timeperiod=15)
        stochf_signal = self.feat.stochf(open_price, high, low, close, timeperiod=20)[0]
        cmf_volume = self.feat.cmf(close, open_price, volume, timeperiod=14)
        long_setup = (close > kama_fast) & (stochf_signal < 35.0) & (cmf_volume > -0.2)
        short_setup = (close < kama_fast) & (stochf_signal > 65.0) & (cmf_volume < 0.1)
        exit_long = close <= kama_fast - 1.8 * self.feat.atr(high, low, close, timeperiod=20)
        exit_short = close >= kama_fast + 1.8 * self.feat.atr(high, low, close, timeperiod=20)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)