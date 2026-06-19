from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 22)
        self.slope_threshold_long = float(self.slope_threshold_long if 'slope_threshold_long' in self.__dict__ else 1.5)
        adx_threshold = self.adx_threshold
        slope_threshold_long = self.slope_threshold_long
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope_val = self.feat.linearreg_slope(close, timeperiod=15)
        adx_val = self.feat.adx(high, low, close, timeperiod=14, smoothbar=35)
        ema_20 = self.feat.ema(close, timeperiod=20)
        long_setup = (close > open_price) & (slope_val >= 0) & (adx_val >= adx_threshold)
        short_setup = (close < open_price) & (slope_val <= 0) & (adx_val >= adx_threshold)
        exit_long = short_entry_signal_triggered | (close < ema_20) & (slope_val < -1.5)
        exit_short = long_entry_signal_triggered | (close > ema_20) & (slope_val > 1.5)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)