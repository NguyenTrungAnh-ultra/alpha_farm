from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.slope_period = int(getattr(self, 'slope_period', 17))
        self.slope_trigger = float(getattr(self, 'slope_trigger', 0.15))
        self.ultosc_offset = float(getattr(self, 'ultosc_offset', 7.0))
        self.natr_min = float(getattr(self, 'natr_min', 0.1))
        self.exit_period = int(getattr(self, 'exit_period', 13))
        self.exit_mult = float(getattr(self, 'exit_mult', 2.5))

        # 2. Local variables for parameters
        slope_period = self.slope_period
        slope_trigger = self.slope_trigger
        ultosc_offset = self.ultosc_offset
        natr_min = self.natr_min
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
        ULTOSC = self.feat.ultosc(high, low, close, timeperiod1=5, timeperiod2=10, timeperiod3=20)
        NATR = self.feat.natr(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Slope > slope_trigger) & (ULTOSC > 50.0 + ultosc_offset) & (NATR > natr_min)
        short_setup = (Slope < -slope_trigger) & (ULTOSC < 50.0 - ultosc_offset) & (NATR > natr_min)

        # 6. Exit logic
        exit_long = (Slope < 0.0) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (Slope > 0.0) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
