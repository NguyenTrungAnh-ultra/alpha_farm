from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.tema_period = 17
        self.var_period = 12
        self.var_sma_period = 25
        self.expansion_factor = 1.85
        self.contraction_factor = 0.7

        # 2. Local variables for parameters
        tema_period = self.tema_period
        var_period = self.var_period
        var_sma_period = self.var_sma_period
        expansion_factor = self.expansion_factor
        contraction_factor = self.contraction_factor

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        TEMA_fast = self.feat.tema(close, timeperiod=tema_period)
        var_raw = self.feat.var(close, timeperiod=var_period)
        var_sma = self.feat.sma(var_raw, timeperiod=var_sma_period)

        # 5. Entry logic
        long_setup = (close > TEMA_fast) & (var_raw > expansion_factor * var_sma)
        short_setup = (close < TEMA_fast) & (var_raw > expansion_factor * var_sma)

        # 6. Exit logic
        exit_long = (close <= TEMA_fast) | (var_raw < contraction_factor * var_sma)
        exit_short = (close >= TEMA_fast) | (var_raw < contraction_factor * var_sma)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
