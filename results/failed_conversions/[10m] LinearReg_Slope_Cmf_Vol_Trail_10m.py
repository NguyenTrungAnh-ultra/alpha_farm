from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 25)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else -1.0)
        slope_period = self.slope_period
        cmf_threshold = self.cmf_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        lrs_slope = self.feat.linearreg_slope(close, timeperiod=20)
        cmf_flow = self.feat.cmf(high, low, close, open_price, volume, timeperiod=50)
        long_setup = (lrs_slope > 0.1) & (cmf_flow >= -1)
        short_setup = (lrs_slope < -0.1) & (cmf_flow <= 1)
        exit_long = (lrs_slope < 0) | (cmf_flow < -2)
        exit_short = (lrs_slope > 0) | (cmf_flow > 2)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)