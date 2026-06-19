from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.t3_period = int(self.t3_period if 't3_period' in self.__dict__ else 30)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.0)
        self.atr_multiplier_k = float(self.atr_multiplier_k if 'atr_multiplier_k' in self.__dict__ else 1.15)
        t3_period = self.t3_period
        cmf_threshold = self.cmf_threshold
        atr_multiplier_k = self.atr_multiplier_k
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        t3_trend = self.feat.t3(close, timeperiod=20)
        cmf_flow = self.feat.cmf(high, low, close, volume, timeperiod=14)
        atr_volatility = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (close > t3_trend) & (cmf_flow >= 0)
        short_setup = (close < t3_trend) & (cmf_flow <= 0)
        exit_long = close < t3_trend - k * atr_volatility
        exit_short = close > t3_trend + k * atr_volatility
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)