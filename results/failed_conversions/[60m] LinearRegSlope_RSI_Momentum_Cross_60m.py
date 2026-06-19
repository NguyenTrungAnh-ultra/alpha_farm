from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_threshold_low = float(self.slope_threshold_low if 'slope_threshold_low' in self.__dict__ else 0.0)
        self.rsi_cross_level_high = int(self.rsi_cross_level_high if 'rsi_cross_level_high' in self.__dict__ else 50)
        slope_threshold_low = self.slope_threshold_low
        rsi_cross_level_high = self.rsi_cross_level_high
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        linearregslope_20 = self.feat.linearreg_slope(close, timeperiod=20)
        rsi_14 = self.feat.rsi(close, timeperiod=14)
        long_setup = (linearregslope_20 > 1.5) & rsi_crossed_above(50)
        short_setup = (linearregslope_20 < -1.5) & rsi_crossed_below(-30)
        exit_long = rsi_crossed_below(50) | (linearregslope_20 <= 1)
        exit_short = rsi_crossed_above(-30) | (linearregslope_20 >= -1)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)