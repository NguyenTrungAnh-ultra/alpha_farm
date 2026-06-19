from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 12)
        self.atr_multiplier = float(self.atr_multiplier if 'atr_multiplier' in self.__dict__ else 1.9)
        bb_period = self.bb_period
        atr_multiplier = self.atr_multiplier
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        bb_upper = self.feat.bbands(close, high, low).upper
        bb_middle = self.feat.bbands(close, high, low).middle
        natr = self.feat.natr(high, low, close)
        long_setup = (close > bb_upper) & (engulfing_pattern == 1)
        short_setup = (close < BB_Lower) & (engulfing_pattern == -1)
        exit_long = close < bb_middle
        exit_short = close > bb_middle
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)