from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.fastk_period = int(self.fastk_period if 'fastk_period' in self.__dict__ else 10)
        self.fastd_period = int(self.fastd_period if 'fastd_period' in self.__dict__ else 3)
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 20)
        self.oversold_threshold = int(self.oversold_threshold if 'oversold_threshold' in self.__dict__ else 20)
        self.overbought_threshold = int(self.overbought_threshold if 'overbought_threshold' in self.__dict__ else 80)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.atr_sma_period = int(self.atr_sma_period if 'atr_sma_period' in self.__dict__ else 35)
        self.volatility_factor = float(self.volatility_factor if 'volatility_factor' in self.__dict__ else 0.75)
        fastk_period = self.fastk_period
        fastd_period = self.fastd_period
        slope_period = self.slope_period
        oversold_threshold = self.oversold_threshold
        overbought_threshold = self.overbought_threshold
        atr_period = self.atr_period
        atr_sma_period = self.atr_sma_period
        volatility_factor = self.volatility_factor
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        stochf_k = self.feat.stochf(high, low, close, fastk_period=10, fastd_period=3)[0]
        stochf_k_prev = self.op.shift(self.op, stochf_k)
        slope = self.feat.linearreg_slope(close, timeperiod=20)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        atr_sma = self.feat.sma(atr, timeperiod=30)
        long_setup = (stochf_k > oversold_threshold) & (stochf_k_prev <= oversold_threshold) & (slope > 0) & (atr > atr_sma * volatility_factor)
        short_setup = (stochf_k < overbought_threshold) & (stochf_k_prev >= overbought_threshold) & (slope < 0) & (atr > atr_sma * volatility_factor)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)