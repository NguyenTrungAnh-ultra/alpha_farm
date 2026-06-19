from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.fast_macd = int(self.fast_macd if 'fast_macd' in self.__dict__ else 18)
        self.slow_macd = int(self.slow_macd if 'slow_macd' in self.__dict__ else 39)
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 10)
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 0.085)
        self.volatility_min = float(self.volatility_min if 'volatility_min' in self.__dict__ else 0.15)
        self.exit_period = int(self.exit_period if 'exit_period' in self.__dict__ else 30)
        fast_macd = self.fast_macd
        slow_macd = self.slow_macd
        slope_period = self.slope_period
        slope_threshold = self.slope_threshold
        volatility_min = self.volatility_min
        exit_period = self.exit_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        macd_hist = self.feat[0](close, fastperiod=fast_macd, slowperiod=slow_macd, signalperiod=9)[2]
        hist_slope = self.feat.linearreg_slope(macd_hist, timeperiod=slope_period)
        natr = self.feat.natr(high, low, close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        midpoint = self.feat.midpoint(close, timeperiod=exit_period)
        long_setup = (hist_slope > slope_threshold) & (natr > volatility_min)
        short_setup = (hist_slope < -slope_threshold) & (natr > volatility_min)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)