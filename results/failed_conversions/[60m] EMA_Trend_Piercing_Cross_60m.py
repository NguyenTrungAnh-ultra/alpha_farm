from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 24)
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 0.0)
        ema_period = self.ema_period
        slope_threshold = self.slope_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=20)
        slope_filter = self.feat.linearreg_slope(close, timeperiod=15)
        long_setup = (close > ema_fast) & (linearreg_slope > 0)
        short_setup = (close < ema_fast) & (linearreg_slope < -2.0)
        exit_long = close < ema_fast
        exit_short = close > ema_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)