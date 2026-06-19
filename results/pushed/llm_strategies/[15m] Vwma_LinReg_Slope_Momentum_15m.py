from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.vwap_period = 100
        self.slope_threshold = 1.0
        vwap_period = self.vwap_period
        slope_threshold = self.slope_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        vwap_trend = self.feat.rolling_vwap(open_price, high, low, close)
        price_angle = self.feat.linearreg_slope(close)
        long_setup = (close > vwap_trend) & (price_angle > 0)
        short_setup = (close < vwap_trend) & (price_angle < 0)
        exit_long = price_angle <= -1.5
        exit_short = price_angle >= 1.5
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
