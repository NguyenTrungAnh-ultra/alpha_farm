from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.trima_period = 10
        self.willr_period = 10
        self.squeeze_factor = 1.0
        self.exit_period = 30
        trima_period = self.trima_period
        willr_period = self.willr_period
        squeeze_factor = self.squeeze_factor
        exit_period = self.exit_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trima = self.feat.trima(close, timeperiod=trima_period)
        willr = self.feat.willr(high, low, close, timeperiod=willr_period)
        stddev_fast = self.feat.stddev(close, timeperiod=10)
        atr = self.feat.atr(high, low, close, timeperiod=20)
        midpoint_exit = self.feat.midpoint(close, timeperiod=exit_period)
        long_setup = (close > trima) & (willr > -30.0) & (stddev_fast > atr * squeeze_factor)
        short_setup = (close < trima) & (willr < -70.0) & (stddev_fast > atr * squeeze_factor)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
