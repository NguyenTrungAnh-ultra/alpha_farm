from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 35)
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 22)
        adx_threshold = self.adx_threshold
        bb_period = self.bb_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        bb_upper = self.feat.bbands(close, high, low, timeperiod=20).upper
        adx_value = self.feat.adx(high, low, close, timeperiod=14)
        ema_slow = self.feat.ema(close, timeperiod=50)
        long_setup = self.feat.engulfing_pattern(open_price, high, close) & (close > bb_upper) & (adx_value >= 18)
        short_setup = self.feat.engulfing_pattern(low, low, open_price) & (close < BB_Lower) & (adx_value >= 15)
        exit_long = close < ema_slow
        exit_short = close > ema_slow
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)