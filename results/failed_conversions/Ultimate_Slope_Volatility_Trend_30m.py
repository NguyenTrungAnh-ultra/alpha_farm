from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ult_period1 = int(self.ult_period1 if 'ult_period1' in self.__dict__ else 7)
        self.ult_period2 = int(self.ult_period2 if 'ult_period2' in self.__dict__ else 15)
        self.ult_period3 = int(self.ult_period3 if 'ult_period3' in self.__dict__ else 30)
        self.natr_period = int(self.natr_period if 'natr_period' in self.__dict__ else 15)
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 20)
        self.volatility_threshold = float(self.volatility_threshold if 'volatility_threshold' in self.__dict__ else 1.25)
        self.ult_oversold = int(self.ult_oversold if 'ult_oversold' in self.__dict__ else 27)
        self.ult_overbought = int(self.ult_overbought if 'ult_overbought' in self.__dict__ else 72)
        self.ult_exit_level = int(self.ult_exit_level if 'ult_exit_level' in self.__dict__ else 50)
        ult_period1 = self.ult_period1
        ult_period2 = self.ult_period2
        ult_period3 = self.ult_period3
        natr_period = self.natr_period
        slope_period = self.slope_period
        volatility_threshold = self.volatility_threshold
        ult_oversold = self.ult_oversold
        ult_overbought = self.ult_overbought
        ult_exit_level = self.ult_exit_level
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ult = self.feat.ultosc(high, low, close, timeperiod1=self.param_ult_period1, timeperiod2=self.param_ult_period2, timeperiod3=self.param_ult_period3)
        slope = self.feat.linearreg_slope(close, timeperiod=self.param_slope_period)
        natr = self.feat.natr(high, low, close, timeperiod=self.param_natr_period)
        long_setup = self.op.crossed_above(ult, self.param_ult_oversold) & (slope > 0) & (natr > self.param_volatility_threshold)
        short_setup = self.op.crossed_below(ult, self.param_ult_overbought) & (slope < 0) & (natr > self.param_volatility_threshold)
        exit_long = (ult < self.param_ult_exit_level) | (slope < 0)
        exit_short = (ult > self.param_ult_exit_level) | (slope > 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)