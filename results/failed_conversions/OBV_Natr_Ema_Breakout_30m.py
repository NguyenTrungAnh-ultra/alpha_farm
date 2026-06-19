from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 21)
        self.obv_sma_period = int(self.obv_sma_period if 'obv_sma_period' in self.__dict__ else 32)
        ema_period = self.ema_period
        obv_sma_period = self.obv_sma_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=10)
        obv_sma = self.feat.sma(self.feat.obv(volume), timeperiod=20)
        long_setup = (close > ema_fast) & obv_cross_above(OBV, obv_sma) & (feat.adx(close, high, low, volume, timeperiod=14) > 25)
        short_setup = (close < ema_fast) & obv_cross_below(OBV, obv_sma) & (feat.adx(close, high, low, volume, timeperiod=14) > 25)
        exit_long = close <= self.feat.ema(close)
        exit_short = close >= self.feat.ema(close)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)