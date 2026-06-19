from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 22)
        self.stochrsi_period = int(self.stochrsi_period if 'stochrsi_period' in self.__dict__ else 16)
        self.long_threshold = float(self.long_threshold if 'long_threshold' in self.__dict__ else 0.925)
        bb_period = self.bb_period
        stochrsi_period = self.stochrsi_period
        long_threshold = self.long_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        stochrsi_val = self.feat.stochrsi(close, timeperiod=14)[0]
        bb_upper = self.feat.bbands(high, low, close, timeperiod=20).upper
        bb_middle = self.feat.bbands(high, low, close, timeperiod=20).middle
        long_setup = (close < bb_lower) & (stochrsi_val <= 50)
        short_setup = (close > bb_upper) & (stochrsi_val >= 50)
        exit_long = (close >= bb_middle) | (not entry_long)
        exit_short = (close <= bb_middle) | (not entry_short)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)