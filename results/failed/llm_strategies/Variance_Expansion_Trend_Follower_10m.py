from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.fast_period = 50
        self.slow_period = 20
        self.var_period = 60
        self.var_ma_period = 5
        self.var_contraction_mult = 0.49
        fast_period = self.fast_period
        slow_period = self.slow_period
        var_period = self.var_period
        var_ma_period = self.var_ma_period
        var_contraction_mult = self.var_contraction_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=10)
        ema_slow = self.feat.ema(close, timeperiod=30)
        var_short = self.feat.var(close, timeperiod=20)
        var_ma = self.feat.sma(var_short, timeperiod=50)
        long_setup = (ema_fast > ema_slow) & (close > ema_fast) & (var_short > var_ma)
        short_setup = (ema_fast < ema_slow) & (close < ema_fast) & (var_short > var_ma)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
