from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.natr_period = int(self.natr_period if 'natr_period' in self.__dict__ else 20)
        self.roc_period = int(self.roc_period if 'roc_period' in self.__dict__ else 5)
        natr_period = self.natr_period
        roc_period = self.roc_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        natr_expansion = self.feat.natr(high, low, close, timeperiod=15)
        roc_momentum = self.feat.roc(close, timeperiod=5)
        volatility_mean = op.rolling_mean(natr_expansion, timeperiod=20)
        long_setup = (natr_expansion > volatility_mean) & (roc_momentum > 0)
        short_setup = (natr_expansion < volatility_mean) & (roc_momentum <= 0)
        exit_long = (close >= open_price) | (volatility_mean > natr_expansion)
        exit_short = (close < open_price) | (volatility_mean < natr_expansion)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)