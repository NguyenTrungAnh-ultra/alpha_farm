from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 22)
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 16)
        bb_period = self.bb_period
        slope_period = self.slope_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        bb_upper = self.feat.bbands(close, timeperiod=20).upper
        bb_middle = self.feat.bbands(close, timeperiod=20).middle
        slope_close = self.feat.linearreg_slope(close, period=15)
        band_width = bb_upper - bb_middle
        long_setup = (close > bb_upper) & (slope_close >= 0)
        short_setup = (close < bb_middle) & (slope_close <= 0)
        exit_long = close < bb_middle
        exit_short = close > bb_middle
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)