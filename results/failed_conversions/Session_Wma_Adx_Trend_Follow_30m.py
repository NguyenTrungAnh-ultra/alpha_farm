from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.wma_period = int(self.wma_period if 'wma_period' in self.__dict__ else 17)
        self.adx_threshold = float(self.adx_threshold if 'adx_threshold' in self.__dict__ else 30.0)
        wma_period = self.wma_period
        adx_threshold = self.adx_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        wma_fast = self.feat.wma(close, timeperiod=10)
        adx_regime = self.feat.adx(high, low, close, volume, timeperiod=14)
        long_setup = (close >= wma_fast) & (adx_regime > 25)
        short_setup = (close <= wma_fast) & (adx_regime > 25)
        exit_long = close < wma_fast
        exit_short = close > wma_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)