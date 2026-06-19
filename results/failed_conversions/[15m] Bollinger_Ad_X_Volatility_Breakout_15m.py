from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = float(self.adx_threshold if 'adx_threshold' in self.__dict__ else 21.0)
        adx_threshold = self.adx_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        bb_upper = self.feat.bbands(high, low, close).upper
        bb_lower = self.feat.bbands(high, low, close).lower
        bb_middle = self.feat.bbands(high, low, close).middle
        adx_strength = self.feat.adx()
        long_setup = (close > bb_upper) & (adx_strength > adx_threshold)
        short_setup = (close < bb_lower) & (adx_strength > adx_threshold)
        exit_long = (close <= bb_middle) | (close >= high[1])
        exit_short = (close >= bb_middle) | (close <= low[1])
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)