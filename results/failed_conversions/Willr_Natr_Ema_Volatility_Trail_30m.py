from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 25)
        self.willr_threshold_long = float(self.willr_threshold_long if 'willr_threshold_long' in self.__dict__ else -80.0)
        ema_period = self.ema_period
        willr_threshold_long = self.willr_threshold_long
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_20 = self.feat.ema(close, timeperiod=20)
        natr_vol = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > ema_20) & (willr < -85)
        short_setup = (close < ema_20) & (willr > 95)
        exit_long = natr_vol < threshold_natr
        exit_short = natr_vol < threshold_natr
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)