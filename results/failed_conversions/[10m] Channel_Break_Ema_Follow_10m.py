from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period_1 = int(self.ema_period_1 if 'ema_period_1' in self.__dict__ else 17)
        self.ema_slow_period = int(self.ema_slow_period if 'ema_slow_period' in self.__dict__ else 40)
        ema_period_1 = self.ema_period_1
        ema_slow_period = self.ema_slow_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=12)
        bb_upper = self.feat.bbands(high, low, close).upper
        bb_lower = self.feat.bbands(high, low, close).lower
        long_setup = (close >= bb_upper) & (ema_fast > self.feat.ema(20))
        short_setup = (close <= bb_lower) & (ema_fast < self.feat.ema(20))
        exit_long = close < bb_middle
        exit_short = close > bb_middle
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)