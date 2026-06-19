from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.vwap_period = int(self.vwap_period if 'vwap_period' in self.__dict__ else 9)
        self.atr_mult = float(self.atr_mult if 'atr_mult' in self.__dict__ else 0.9)
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 9)
        vwap_period = self.vwap_period
        atr_mult = self.atr_mult
        slope_period = self.slope_period
        open_price = self.data.pv_open
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        vwap = self.feat.rolling_vwap(high, low, close, volume, timeperiod=vwap_period)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        slope = self.feat.linearreg_slope(close, timeperiod=slope_period)
        long_setup = (close > vwap + atr_mult * atr) & (slope > 0) & (atr > 0.5)
        short_setup = (close < vwap - atr_mult * atr) & (slope < 0) & (atr > 0.5)
        exit_long = (close < vwap) | (slope < 0)
        exit_short = (close > vwap) | (slope > 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)