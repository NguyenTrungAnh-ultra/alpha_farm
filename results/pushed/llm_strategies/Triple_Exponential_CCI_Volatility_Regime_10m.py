from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.tema_period = 100
        self.cci_period = 30
        self.cci_bound = 66.5
        self.natr_min = 0.1
        self.exit_period = 5
        self.exit_mult = 3.4799999999999995
        tema_period = self.tema_period
        cci_period = self.cci_period
        cci_bound = self.cci_bound
        natr_min = self.natr_min
        exit_period = self.exit_period
        exit_mult = self.exit_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        tema = self.feat.tema(close, timeperiod=tema_period)
        cci_fast = self.feat.cci(high, low, close, timeperiod=cci_period)
        cci_smooth = self.feat.wma(cci_fast, timeperiod=5)
        natr = self.feat.natr(high, low, close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        rolling_max = self.feat.max(high, timeperiod=exit_period)
        rolling_min = self.feat.min(low, timeperiod=exit_period)
        long_setup = (close > tema) & (cci_smooth > cci_bound) & (natr > natr_min)
        short_setup = (close < tema) & (cci_smooth < -cci_bound) & (natr > natr_min)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
