from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.vwap_period = int(self.vwap_period if 'vwap_period' in self.__dict__ else 30)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.0)
        vwap_period = self.vwap_period
        cmf_threshold = self.cmf_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        rollingvwap = self.feat.rolling_vwap(close)
        cmf = self.feat.cmf(volume, timeperiod=20)
        natr = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > rollingvwap) & (cmf > 0.5) | (natr < threshold)
        short_setup = (close < rollingvwap) & (cmf < -0.5) | (natr < threshold)
        exit_long = self.op.crossed_below(close, rollingvwap)
        exit_short = self.op.crossed_above(close, rollingvwap)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)