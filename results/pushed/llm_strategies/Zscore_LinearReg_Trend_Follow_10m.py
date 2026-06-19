from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.lr_period = 60
        self.zscore_threshold_long = float(self.zscore_threshold_long if 'zscore_threshold_long' in self.__dict__ else -1.25)
        lr_period = self.lr_period
        zscore_threshold_long = self.zscore_threshold_long
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trend_line = self.feat.linearreg(close, timeperiod=50)
        zscore = self.feat.rolling_zscore(close, window=30)
        long_setup = (close >= trend_line) & (zscore > -1)
        short_setup = (close <= trend_line) & (zscore < 1)
        exit_long = close < trend_line
        exit_short = close > trend_line
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
