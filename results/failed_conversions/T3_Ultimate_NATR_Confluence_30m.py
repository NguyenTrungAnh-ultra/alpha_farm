from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.t3_period = int(self.t3_period if 't3_period' in self.__dict__ else 40)
        self.natr_threshold = float(self.natr_threshold if 'natr_threshold' in self.__dict__ else 20.0)
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 6)
        t3_period = self.t3_period
        natr_threshold = self.natr_threshold
        slope_period = self.slope_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        t3 = self.feat.t3(close, timeperiod={t3_period}, vfactor=0.7)
        t3_shift = self.op.shift(t3, {slope_period})
        ult = self.feat.ultosc(high, low, close, timeperiod1=7, timeperiod2=14, timeperiod3=28)
        natr = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (t3 > t3_shift) & (ult < 30) & (natr > {natr_threshold})
        short_setup = (t3 < t3_shift) & (ult > 70) & (natr > {natr_threshold})
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)