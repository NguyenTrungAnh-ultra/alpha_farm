from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.trima_period = int(self.trima_period if 'trima_period' in self.__dict__ else 17)
        self.rsi_threshold_long = float(self.rsi_threshold_long if 'rsi_threshold_long' in self.__dict__ else 55.0)
        self.atr_multiplier = float(self.atr_multiplier if 'atr_multiplier' in self.__dict__ else 1.75)
        trima_period = self.trima_period
        rsi_threshold_long = self.rsi_threshold_long
        atr_multiplier = self.atr_multiplier
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trima = self.feat.trima(close)
        sma_20 = self.feat.sma(close, timeperiod=20)
        rsi = self.feat.rsi(high, low, close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (trima > sma_20) & (rsi < 65)
        short_setup = (trima < sma_20) & (rsi > 35)
        exit_long = close < sma_20 - atr * param1
        exit_short = close > sma_20 + atr * param1
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)