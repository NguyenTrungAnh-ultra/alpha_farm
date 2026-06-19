from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 22)
        self.cmf_threshold_low = float(self.cmf_threshold_low if 'cmf_threshold_low' in self.__dict__ else -0.075)
        ema_period = self.ema_period
        cmf_threshold_low = self.cmf_threshold_low
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=20)
        ultosc_momentum = self.feat.ultrasc(high, low, close, length=14)
        cmf_volume = self.feat.cmf(open_price, high, low, volume, timeperiod=20)
        bb_upper = self.feat.bbands(close, 20, 3.0).upper
        bb_lower = self.feat.bbands(high, low, close, timeperiod=20).lower
        long_setup = (close >= ema_fast) & (ultosc_momentum > rolling_min(ema_fast, 15)) & (cmf_volume > -0.05)
        short_setup = (close <= ema_fast) & (ultosc_momentum < rolling_max(ema_fast, 15)) & (cmf_volume < 0.05)
        exit_long = close < bb_lower
        exit_short = close > bb_upper
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)