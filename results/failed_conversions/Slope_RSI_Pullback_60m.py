from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.rsi_period = int(self.rsi_period if 'rsi_period' in self.__dict__ else 17)
        self.slope_threshold_long = float(self.slope_threshold_long if 'slope_threshold_long' in self.__dict__ else 0.6)
        rsi_period = self.rsi_period
        slope_threshold_long = self.slope_threshold_long
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope_trend = self.feat.linearreg_slope(close, timeperiod=10)
        rsi_momentum = self.feat.rsi(close, timeperiod=14)
        long_setup = (linearreg_slope > 0.5) & (rsi < 48)
        short_setup = (linearreg_slope < -0.5) & (rsi > 52)
        exit_long = (close < self.feat.ema(close, timeperiod=20)) | (slope_trend <= -1)
        exit_short = (close > self.feat.ema(close, timeperiod=20)) | (slope_trend >= 1)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)