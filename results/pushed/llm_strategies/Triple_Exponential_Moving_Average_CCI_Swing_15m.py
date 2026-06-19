from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.tema_period = 60
        self.cci_period = 10
        self.cci_bound = 54.0
        self.expansion_mult = 0.65
        self.exit_period = 20
        self.exit_mult = 4.199999999999999
        tema_period = self.tema_period
        cci_period = self.cci_period
        cci_bound = self.cci_bound
        expansion_mult = self.expansion_mult
        exit_period = self.exit_period
        exit_mult = self.exit_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        tema = self.feat.tema(close, timeperiod=tema_period)
        cci_raw = self.feat.cci(high, low, close, timeperiod=cci_period)
        cci_smooth = self.feat.wma(cci_raw, timeperiod=5)
        volatility_fast = self.feat.stddev(close, timeperiod=10)
        volatility_base = self.feat.sma(volatility_fast, timeperiod=30)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        rolling_max = self.feat.max(high, timeperiod=exit_period)
        rolling_min = self.feat.min(low, timeperiod=exit_period)
        long_setup = (close > tema) & (cci_smooth > cci_bound) & (volatility_fast > volatility_base * expansion_mult)
        short_setup = (close < tema) & (cci_smooth < -cci_bound) & (volatility_fast > volatility_base * expansion_mult)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
