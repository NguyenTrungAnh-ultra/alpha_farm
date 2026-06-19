from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 14)
        self.stoch_k_period = int(self.stoch_k_period if 'stoch_k_period' in self.__dict__ else 5)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.15)
        ema_period = self.ema_period
        stoch_k_period = self.stoch_k_period
        cmf_threshold = self.cmf_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=14)
        stochf_fast = self.feat.stochf(open_price, high, low, close, timeperiod=5, fast_period=3)[0]
        cmf_volflow = self.feat.cmf(volume, open_price)
        long_setup = (close > ema_fast) & (cmf_volflow > 0.15) & self.op.crossed_above(self.op.shift(self.op, stochf_fast, 1), stochf_fast)
        short_setup = (close < ema_fast) & (cmf_volflow < -0.15) & self.op.crossed_below(self.op.shift(self.op, stochf_fast, 1), stochf_fast)
        exit_long = close < ema_fast
        exit_short = close > ema_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)