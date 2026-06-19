from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 1.25)
        self.cci_cross_level = float(self.cci_cross_level if 'cci_cross_level' in self.__dict__ else -5.0)
        slope_threshold = self.slope_threshold
        cci_cross_level = self.cci_cross_level
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trend_slope = self.feat.linearreg_slope(close, timeperiod=20)
        cci_filter = self.feat.cci(high, low, close, timeperiod=14)
        natr_exit = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (trend_slope > 0.5) & cci_filter_crossed_above(-20)
        short_setup = (trend_slope < -0.5) & cci_filter_crossed_below(20)
        exit_long = (close < close_prev * (1 + natr_exit * 0.3)) | (trend_slope <= 0)
        exit_short = (close > close_prev * (1 - natr_exit * 0.3)) | (trend_slope >= 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)