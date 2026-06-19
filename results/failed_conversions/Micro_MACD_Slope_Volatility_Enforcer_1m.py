from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 7)
        self.slope_trigger = float(self.slope_trigger if 'slope_trigger' in self.__dict__ else 0.09)
        self.expansion_factor = float(self.expansion_factor if 'expansion_factor' in self.__dict__ else 1.3)
        self.exit_period = int(self.exit_period if 'exit_period' in self.__dict__ else 4)
        slope_period = self.slope_period
        slope_trigger = self.slope_trigger
        expansion_factor = self.expansion_factor
        exit_period = self.exit_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        macd_hist = self.feat[0](close, fastperiod=12, slowperiod=26, signalperiod=9)[2]
        hist_slope = self.feat.linearreg_slope(macd_hist, timeperiod=slope_period)
        tr = self.feat.trange(high, low, close)
        tr_smooth = self.feat.sma(tr, timeperiod=20)
        micro_high = self.feat.max(high, timeperiod=exit_period)
        micro_low = self.feat.min(low, timeperiod=exit_period)
        long_setup = (hist_slope > slope_trigger) & (tr > tr_smooth * expansion_factor)
        short_setup = (hist_slope < -slope_trigger) & (tr > tr_smooth * expansion_factor)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)