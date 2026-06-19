from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.timeperiod_slope = int(self.timeperiod_slope if 'timeperiod_slope' in self.__dict__ else 25)
        self.slope_threshold_long = float(self.slope_threshold_long if 'slope_threshold_long' in self.__dict__ else 0.5)
        self.timeperiod_bbands = int(self.timeperiod_bbands if 'timeperiod_bbands' in self.__dict__ else 22)
        timeperiod_slope = self.timeperiod_slope
        slope_threshold_long = self.slope_threshold_long
        timeperiod_bbands = self.timeperiod_bbands
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope = self.feat.linearreg_slope(close, timeperiod=20)
        bbands_upper = self.feat.bbands(high, low, close, timeperiod=14).upper
        bbands_lower = self.feat.bbands(high, low, close, timeperiod=14).lower
        regression_line = self.feat.linearreg(close, timeperiod=20)
        long_setup = (close > bbands_upper) & (slope > 0.5)
        short_setup = (close < bbands_lower) & (slope < -0.5)
        exit_long = (close <= regression_line) | (close < bbands_upper)
        exit_short = (close >= regression_line) | (close > bbands_lower)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)