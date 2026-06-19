from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.fast_period = int(self.fast_period if 'fast_period' in self.__dict__ else 10)
        self.slow_period = int(self.slow_period if 'slow_period' in self.__dict__ else 50)
        fast_period = self.fast_period
        slow_period = self.slow_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=fast_period)
        ema_slow = self.feat.ema(close, timeperiod=slow_period)
        long_setup = (close > ema_slow) & (ema_fast > ema_slow)
        short_setup = (close < ema_slow) & (ema_fast < ema_slow)
        exit_long = close < ema_fast
        exit_short = close > ema_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)