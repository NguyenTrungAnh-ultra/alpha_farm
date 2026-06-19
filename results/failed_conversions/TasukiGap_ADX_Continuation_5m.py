from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 25)
        self.atr_exit_mult = float(self.atr_exit_mult if 'atr_exit_mult' in self.__dict__ else 2.25)
        adx_threshold = self.adx_threshold
        atr_exit_mult = self.atr_exit_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        adx = self.feat.adx(high, low, close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        bullish_tasuki = self.feat.tasukigap_pattern(open_price, high, low, close) == 100
        bearish_tasuki = self.feat.tasukigap_pattern(open_price, high, low, close) == -100
        rolling_high_max = self.feat.max(high, timeperiod=10)
        rolling_low_min = self.feat.min(low, timeperiod=10)
        long_setup = bullish_tasuki & (adx > adx_threshold)
        short_setup = bearish_tasuki & (adx > adx_threshold)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)