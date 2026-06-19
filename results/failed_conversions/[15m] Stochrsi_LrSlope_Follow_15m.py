from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 1.5)
        self.stoch_length = int(self.stoch_length if 'stoch_length' in self.__dict__ else 22)
        slope_threshold = self.slope_threshold
        stoch_length = self.stoch_length
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        lr_slope = self.feat.linearreg_slope(close, timeperiod=20)
        stochrsi = self.feat.stochrsi(close, length14, k3, d3)[0]
        long_setup = (linearreg_slope > 0.5) & stochrsi_crossed_above(self.op.shift(self.op, stochrsi, timeperiod=2))
        short_setup = (linearreg_slope < -0.5) & stochrsi_crossed_below(self.op.shift(self.op, stochrsi, timeperiod=2))
        exit_long = (close < self.feat.linearreg(close)) | (linearreg_slope <= 0)
        exit_short = (close > self.feat.linearreg(close)) | (linearreg_slope >= 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)