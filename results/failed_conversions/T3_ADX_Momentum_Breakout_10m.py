from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_min = float(self.slope_min if 'slope_min' in self.__dict__ else 0.0)
        self.natr_threshold = int(self.natr_threshold if 'natr_threshold' in self.__dict__ else 30)
        slope_min = self.slope_min
        natr_threshold = self.natr_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=15)
        t3_trend = self.feat.t3(close, timeperiod=20)
        adx_strength = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (close > ema_fast) & (self.feat.linearreg_slope(t3_trend, 5) >= slope_min)
        short_setup = (close < ema_fast) & (self.feat.linearreg_slope(t3_trend, 5) <= -slope_min)
        exit_long = (self.feat.natr(high, low, close, timeperiod=14) <= natr_threshold) | (adx_strength <= adx_max)
        exit_short = (self.feat.natr(high, low, close, timeperiod=14) >= natr_high_limit) & (adx_strength < 25)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)