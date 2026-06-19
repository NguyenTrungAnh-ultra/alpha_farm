from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 10.0)
        self.stochrsi_low = int(self.stochrsi_low if 'stochrsi_low' in self.__dict__ else 55)
        slope_threshold = self.slope_threshold
        stochrsi_low = self.stochrsi_low
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope = self.feat.linearreg_slope(close, timeperiod=40)
        stochrsi_val = self.feat.stochrsi(midprice)[0]
        long_setup = (slope > 1.5) & (close < midpoint + slope_threshold)
        short_setup = (slope < -1.5) & (close > midpoint - slope_threshold)
        exit_long = (stochrsi_val > 80) | (slope < -2.0)
        exit_short = (stochrsi_val < 20) | (slope > 2.0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)