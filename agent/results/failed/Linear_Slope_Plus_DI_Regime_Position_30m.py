from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.slope_period = int(getattr(self, 'slope_period', 40))
        self.slope_threshold = float(getattr(self, 'slope_threshold', 0.15))
        self.di_period = int(getattr(self, 'di_period', 21))
        self.expansion_factor = float(getattr(self, 'expansion_factor', 0.95))
        self.exit_period = int(getattr(self, 'exit_period', 22))
        self.exit_mult = float(getattr(self, 'exit_mult', 3.5))

        # 2. Local variables for parameters
        slope_period = self.slope_period
        slope_threshold = self.slope_threshold
        di_period = self.di_period
        expansion_factor = self.expansion_factor
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Slope = self.feat.linearreg_slope(close, timeperiod=slope_period)
        Plus_DI = self.feat.plus_di(high, low, close, timeperiod=di_period)
        Minus_DI = self.feat.minus_di(high, low, close, timeperiod=di_period)
        Volatility_Fast = self.feat.stddev(close, timeperiod=10)
        ATR = self.feat.atr(high, low, close, timeperiod=20)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Slope > slope_threshold) & (Plus_DI > Minus_DI) & (Volatility_Fast > ATR * expansion_factor)
        short_setup = (Slope < -slope_threshold) & (Minus_DI > Plus_DI) & (Volatility_Fast > ATR * expansion_factor)

        # 6. Exit logic
        exit_long = (Slope < 0.0) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (Slope > 0.0) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
