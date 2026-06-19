from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 0.55)
        self.ema_roc_period = int(self.ema_roc_period if 'ema_roc_period' in self.__dict__ else 14)
        slope_threshold = self.slope_threshold
        ema_roc_period = self.ema_roc_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope_20 = self.feat.linearreg_slope(close, timeperiod=20)
        roc_14 = self.feat.roc(close, timeperiod=14)
        ema_roc_mean = self.feat.ema(self.indicators['roc_14'], timeperiod=5)
        natr_volatility = self.feat.natr(high, low, close, timeperiod=20)
        long_setup = (slope_20 > 0.3) & roc_crossed_above(ema_roc_mean)
        short_setup = (slope_20 < -0.3) & roc_crossed_below(ema_roc_mean)
        exit_long = natr_volatility > natr_ma(natr_volatility, timeperiod=5)
        exit_short = natr_volatility > natr_ma(natr_volatility, timeperiod=5)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)