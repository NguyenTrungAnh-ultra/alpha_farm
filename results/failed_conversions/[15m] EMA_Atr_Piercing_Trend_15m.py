from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 14)
        self.atr_period = float(self.atr_period if 'atr_period' in self.__dict__ else 24.5)
        ema_period = self.ema_period
        atr_period = self.atr_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=14)
        atr_filter = self.feat.atr(high, low, close, timeperiod=20)
        long_setup = (close > ema_fast) & (atr_filter < rolling_mean(atr_filter)) & self.op.isna(self.feat.piercing_pattern())
        short_setup = (close < ema_fast) & (atr_filter < rolling_mean(atr_filter)) & ~self.op.isna(self.feat.piercing_pattern(open_price, close))
        exit_long = ema_fast > open_price
        exit_short = ema_fast < open_price
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)