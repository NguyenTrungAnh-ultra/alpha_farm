from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.trend_period = int(self.trend_period if 'trend_period' in self.__dict__ else 22)
        self.osc_fast = int(self.osc_fast if 'osc_fast' in self.__dict__ else 6)
        self.osc_slow = int(self.osc_slow if 'osc_slow' in self.__dict__ else 16)
        trend_period = self.trend_period
        osc_fast = self.osc_fast
        osc_slow = self.osc_slow
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trend_slope = self.feat.linearreg_slope(close, timeperiod=20)
        stochf_val = self.feat.stochf(high, low, close, timeperiod=5)[0]
        osc_trend = self.feat.ema(stochf_val, timeperiod=14)
        long_setup = (self.feat.linearreg_slope(close) > 0) & (self.op.shift(stochf_val, -1) < self.op.shift(osc_trend, -1)) & (stochf_val > osc_trend)
        short_setup = (self.feat.linearreg_slope(close) < 0) & (self.op.shift(stochf_val, -1) > self.op.shift(osc_trend, -1)) & (stochf_val < osc_trend)
        exit_long = self.op.shift(stochf_val, 1) <= self.op.shift(osc_trend, 1)
        exit_short = self.op.shift(stochf_val, 1) >= self.op.shift(osc_trend, 1)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)