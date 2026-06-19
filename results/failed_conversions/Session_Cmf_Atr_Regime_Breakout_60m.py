from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 17)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.3)
        ema_period = self.ema_period
        cmf_threshold = self.cmf_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=10)
        cmf = self.feat.cmf(volume, close, timeperiod=5)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (close > ema_fast) & cmf.crossed_above(0) & (atr < self.op.shift(rolling_max(atr, period=20), -1))
        short_setup = (close < ema_fast) & cmf.crossed_below(0) & (atr < self.op.shift(rolling_min(atr, period=20), -1))
        exit_long = close <= ema_fast
        exit_short = close >= ema_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)