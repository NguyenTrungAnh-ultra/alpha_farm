from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 30)
        ema_period = self.ema_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        macd_line = self.feat.macd(close, fast_period=12, slow_period=26)[0]
        natr = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > self.params.ema_period) & (macd_line < self.op.shift(self.op, macd_line, 2)) & (natr_rolling_mean < natr)
        short_setup = close != close
        exit_long = macd_line >= self.op.shift(self.op, macd_line, 2)
        exit_short = (self.op.shift(self.op, macd_line, -1) >= macd_line) & (self.feat.macd(close)[0] <= close)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)