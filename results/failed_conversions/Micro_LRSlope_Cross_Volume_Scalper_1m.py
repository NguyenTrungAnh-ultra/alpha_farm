from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.fast_len = int(self.fast_len if 'fast_len' in self.__dict__ else 3)
        self.slow_len = int(self.slow_len if 'slow_len' in self.__dict__ else 11)
        self.vol_mult = float(self.vol_mult if 'vol_mult' in self.__dict__ else 1.6)
        self.atr_len = int(self.atr_len if 'atr_len' in self.__dict__ else 7)
        self.atr_mult = float(self.atr_mult if 'atr_mult' in self.__dict__ else 1.75)
        self.trail_len = int(self.trail_len if 'trail_len' in self.__dict__ else 5)
        fast_len = self.fast_len
        slow_len = self.slow_len
        vol_mult = self.vol_mult
        atr_len = self.atr_len
        atr_mult = self.atr_mult
        trail_len = self.trail_len
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        fast_slope = self.feat.linearreg_slope(close, timeperiod=fast_len)
        slow_slope = self.feat.linearreg_slope(close, timeperiod=slow_len)
        fast_slope_prev = self.op.shift(self.feat, fast_slope)
        slow_slope_prev = self.op.shift(self.feat, slow_slope)
        volume_sma = self.feat.sma(volume, timeperiod=20)
        atr = self.feat.atr(high, low, close, timeperiod=atr_len)
        trail_high = self.feat.highest(close, timeperiod=trail_len)
        trail_low = self.feat.lowest(close, timeperiod=trail_len)
        long_setup = (fast_slope > slow_slope) & (fast_slope_prev <= slow_slope_prev) & (volume > volume_sma * vol_mult) & (fast_slope > 0)
        short_setup = (fast_slope < slow_slope) & (fast_slope_prev >= slow_slope_prev) & (volume > volume_sma * vol_mult) & (fast_slope < 0)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)