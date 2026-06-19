from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 24)
        self.channel_period = int(self.channel_period if 'channel_period' in self.__dict__ else 22)
        adx_threshold = self.adx_threshold
        channel_period = self.channel_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        channel_upper = self.op.rolling_max(high, timeperiod=20)
        channel_lower = self.op.rolling_min(low, timeperiod=20)
        adx_trend = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (close > channel_upper) & (adx_trend > 25)
        short_setup = (close < channel_lower) & (adx_trend > 25)
        exit_long = close <= channel_upper
        exit_short = close >= channel_lower
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)