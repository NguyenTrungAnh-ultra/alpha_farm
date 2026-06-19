from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 30)
        self.stoch_k1 = float(self.stoch_k1 if 'stoch_k1' in self.__dict__ else 6.0)
        ema_period = self.ema_period
        stoch_k1 = self.stoch_k1
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=20)
        stoch_fast = self.feat.stoch(high, low, close)[0]
        long_setup = (close > ema_fast) & op.crossed_above(stoch_fast)
        short_setup = (close < ema_fast) & op.crossed_below(stoch_fast)
        exit_long = close < ema_fast
        exit_short = close > ema_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)