from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.trima_period = 5
        self.aroon_period = 10
        self.atr_period = 5
        self.trailing_period = 20
        self.atr_multiplier = 1.5
        trima_period = self.trima_period
        aroon_period = self.aroon_period
        atr_period = self.atr_period
        trailing_period = self.trailing_period
        atr_multiplier = self.atr_multiplier
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trima = self.feat.trima(close, timeperiod=20)
        aroonosc = self.feat.aroonosc(high, low, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        rolling_high_max = self.feat.rolling_max(high, window=10)
        rolling_low_min = self.feat.rolling_min(low, window=10)
        long_setup = (aroonosc > 0) & (close > trima)
        short_setup = (aroonosc < 0) & (close < trima)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
