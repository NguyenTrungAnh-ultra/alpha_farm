from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 20)
        self.zscore_threshold = float(self.zscore_threshold if 'zscore_threshold' in self.__dict__ else 1.5)
        ema_period = self.ema_period
        zscore_threshold = self.zscore_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        tema_trend = self.feat.tema(close, timeperiod=20)
        zscore_momentum = self.feat.rolling_zscore(close, period=15)
        natr_volatility = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > tema_trend) & (zscore_momentum > 0.8)
        short_setup = (close < tema_trend) & (zscore_momentum < -0.8)
        exit_long = (close <= tema_trend) | (natr_volatility < rolling_min(natr_volatility, period=15))
        exit_short = (close >= tema_trend) | (natr_volatility < rolling_min(natr_volatility, period=15))
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)