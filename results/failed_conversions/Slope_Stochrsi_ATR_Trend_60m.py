from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_threshold_long = int(self.slope_threshold_long if 'slope_threshold_long' in self.__dict__ else 12)
        self.slope_threshold_short = int(self.slope_threshold_short if 'slope_threshold_short' in self.__dict__ else -10)
        self.stochrsi_entry_long = float(self.stochrsi_entry_long if 'stochrsi_entry_long' in self.__dict__ else 30.0)
        slope_threshold_long = self.slope_threshold_long
        slope_threshold_short = self.slope_threshold_short
        stochrsi_entry_long = self.stochrsi_entry_long
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope_20 = self.feat.linearreg_slope(close, timeperiod=20)
        stochrsi_val = self.feat.stochrsi(high, low, close, length14, timeperiod=3)[0]
        atr_14 = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (slope_20 > 5.0) & (stochrsi_val < 30)
        short_setup = (slope_20 < -5.0) & (stochrsi_val > 70)
        exit_long = (slope_20 <= -10.0) | (stochrsi_val >= 80)
        exit_short = (slope_20 >= 10.0) | (stochrsi_val <= 20)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)