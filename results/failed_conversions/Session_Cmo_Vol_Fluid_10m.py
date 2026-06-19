from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.cmo_threshold = float(self.cmo_threshold if 'cmo_threshold' in self.__dict__ else 5.5)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 17)
        cmo_threshold = self.cmo_threshold
        atr_period = self.atr_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        cmo = self.feat.cmo(close)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = self.op.shift(self.op, crossed_above_value) & (cmo > 5.0)
        short_setup = self.op.shift(self.op, crossed_below_value) & (cmo < -5.0)
        exit_long = close < self.feat.ema(close, timeperiod=21)
        exit_short = close > self.feat.ema(close, timeperiod=21)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)