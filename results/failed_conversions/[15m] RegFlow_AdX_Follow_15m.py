from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 27)
        self.cmf_period = int(self.cmf_period if 'cmf_period' in self.__dict__ else 19)
        adx_threshold = self.adx_threshold
        cmf_period = self.cmf_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        regline = self.feat.linearreg(close, timeperiod=20)
        cmf = self.feat.cmf(volume, close, timeperiod=14)
        adx = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (close > regline) & (cmf > 0.5)
        short_setup = (close < regline) & (cmf < -0.5)
        exit_long = close <= regline
        exit_short = close >= regline
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)