from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_fast_period = int(self.ema_fast_period if 'ema_fast_period' in self.__dict__ else 23)
        self.atr_mult = float(self.atr_mult if 'atr_mult' in self.__dict__ else 1.4)
        ema_fast_period = self.ema_fast_period
        atr_mult = self.atr_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        macd_histogram = self.feat[0](close)
        atr_fast = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = macd_h > 0.5
        short_setup = macd_h < -0.5
        exit_long = macd_h < 0
        exit_short = macd_h > 0
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)