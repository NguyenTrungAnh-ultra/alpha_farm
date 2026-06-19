from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.fast_period = 12
        self.slow_period = 35
        self.var_period = 20
        self.var_ma_period = 50
        self.var_contraction_mult = 0.7

        # 2. Local variables for parameters
        fast_period = self.fast_period
        slow_period = self.slow_period
        var_period = self.var_period
        var_ma_period = self.var_ma_period
        var_contraction_mult = self.var_contraction_mult

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        EMA_fast = self.feat.ema(close, timeperiod=10)
        EMA_slow = self.feat.ema(close, timeperiod=30)
        VAR_short = self.feat.var(close, timeperiod=20)
        VAR_MA = self.feat.sma(VAR_short, timeperiod=50)

        # 5. Entry logic
        long_setup = (EMA_fast > EMA_slow) & (close > EMA_fast) & (VAR_short > VAR_MA)
        short_setup = (EMA_fast < EMA_slow) & (close < EMA_fast) & (VAR_short > VAR_MA)

        # 6. Exit logic
        exit_long = (EMA_fast < EMA_slow) | (VAR_short < VAR_MA * 0.8)
        exit_short = (EMA_fast > EMA_slow) | (VAR_short < VAR_MA * 0.8)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)


# OPTIMIZATION_V2_COMPLETED
