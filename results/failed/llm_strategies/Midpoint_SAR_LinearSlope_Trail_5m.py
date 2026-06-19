from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.midpoint_period = 20
        self.slope_period = 20
        self.sar_acceleration = 0.03
        self.sar_maximum = 0.26
        midpoint_period = self.midpoint_period
        slope_period = self.slope_period
        sar_acceleration = self.sar_acceleration
        sar_maximum = self.sar_maximum
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        midpoint = self.feat.midpoint(high, low, timeperiod=20)
        slope = self.feat.linearreg_slope(close, timeperiod=20)
        sar = self.feat.sar(high, low, acceleration=0.02, maximum=0.2)
        long_setup = (close > midpoint) & (slope > 0) & (close > sar)
        short_setup = (close < midpoint) & (slope < 0) & (close < sar)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
