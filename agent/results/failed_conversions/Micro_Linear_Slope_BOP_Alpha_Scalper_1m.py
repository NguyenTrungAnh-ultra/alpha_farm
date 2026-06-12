from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.slope_period = int(getattr(self, 'slope_period', 8))
        self.slope_trigger = float(getattr(self, 'slope_trigger', 0.13))
        self.bop_threshold = float(getattr(self, 'bop_threshold', 0.15))
        self.noise_threshold = float(getattr(self, 'noise_threshold', 0.7))
        self.exit_period = int(getattr(self, 'exit_period', 4))

        # 2. Local variables for parameters
        slope_period = self.slope_period
        slope_trigger = self.slope_trigger
        bop_threshold = self.bop_threshold
        noise_threshold = self.noise_threshold
        exit_period = self.exit_period

        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume

        # 4. Indicators
        Slope_Fast = self.feat.linearreg_slope(close, timeperiod=slope_period)
        BOP = self.feat.bop(open, high, low, close)
        BOP_Smooth = self.feat.wma(BOP, timeperiod=5)
        Volatility_Floor = self.feat.stddev(close, timeperiod=10)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Slope_Fast > slope_trigger) & (BOP_Smooth > bop_threshold) & (Volatility_Floor > noise_threshold)
        short_setup = (Slope_Fast < -slope_trigger) & (BOP_Smooth < -bop_threshold) & (Volatility_Floor > noise_threshold)

        # 6. Exit logic
        exit_long = (close < Micro_Low) | (Slope_Fast < 0.0)
        exit_short = (close > Micro_High) | (Slope_Fast > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
