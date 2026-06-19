from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 17)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.0)
        ema_period = self.ema_period
        cmf_threshold = self.cmf_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        vwap_sess = self.feat.rolling_vwap(close, timeperiod=20)
        cmf_flows = self.feat.cmf(volume)
        long_setup = (close > vwap_sess) & (cmf_flows > 0)
        short_setup = (close < vwap_sess) & (cmf_flows < 0)
        exit_long = close <= vwap_sess
        exit_short = close >= vwap_sess
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)