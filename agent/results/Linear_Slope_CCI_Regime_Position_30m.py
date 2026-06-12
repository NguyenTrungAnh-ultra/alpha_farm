from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.slope_period = int(getattr(self, 'slope_period', 26))
        self.slope_threshold = float(getattr(self, 'slope_threshold', 0.09))
        self.cci_period = int(getattr(self, 'cci_period', 16))
        self.cci_bound = float(getattr(self, 'cci_bound', 110.0))
        self.expansion_factor = float(getattr(self, 'expansion_factor', 1.15))
        self.exit_period = int(getattr(self, 'exit_period', 18))

        # 2. Local variables for parameters
        slope_period = self.slope_period
        slope_threshold = self.slope_threshold
        cci_period = self.cci_period
        cci_bound = self.cci_bound
        expansion_factor = self.expansion_factor
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Slope = self.feat.linearreg_slope(close, timeperiod=slope_period)
        CCI = self.feat.cci(high, low, close, timeperiod=cci_period)
        Volatility_Fast = self.feat.stddev(close, timeperiod=10)
        ATR = self.feat.atr(high, low, close, timeperiod=20)
        Midpoint_Exit = self.feat.midpoint(close, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Slope > slope_threshold) & (CCI > cci_bound) & (Volatility_Fast > ATR * expansion_factor)
        short_setup = (Slope < -slope_threshold) & (CCI < -cci_bound) & (Volatility_Fast > ATR * expansion_factor)

        # 6. Exit logic
        exit_long = (close < Midpoint_Exit - 0.25 * ATR) | (Slope < 0.0)
        exit_short = (close > Midpoint_Exit + 0.25 * ATR) | (Slope > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
