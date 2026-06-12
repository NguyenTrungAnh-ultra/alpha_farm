from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.slope_period = int(getattr(self, 'slope_period', 7))
        self.slope_trigger = float(getattr(self, 'slope_trigger', 0.09))
        self.expansion_factor = float(getattr(self, 'expansion_factor', 1.3))
        self.exit_period = int(getattr(self, 'exit_period', 4))

        # 2. Local variables for parameters
        slope_period = self.slope_period
        slope_trigger = self.slope_trigger
        expansion_factor = self.expansion_factor
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        MACD_Hist = self.feat.macd(close, fastperiod=12, slowperiod=26, signalperiod=9)[2]
        Hist_Slope = self.feat.linearreg_slope(MACD_Hist, timeperiod=slope_period)
        TR = self.feat.trange(high, low, close)
        TR_Smooth = self.feat.sma(TR, timeperiod=20)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Hist_Slope > slope_trigger) & (TR > TR_Smooth * expansion_factor)
        short_setup = (Hist_Slope < -slope_trigger) & (TR > TR_Smooth * expansion_factor)

        # 6. Exit logic
        exit_long = (close < Micro_Low) | (Hist_Slope < 0.0)
        exit_short = (close > Micro_High) | (Hist_Slope > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
