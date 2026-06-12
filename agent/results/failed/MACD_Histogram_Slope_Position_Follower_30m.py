from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.fast_macd = int(getattr(self, 'fast_macd', 18))
        self.slow_macd = int(getattr(self, 'slow_macd', 39))
        self.slope_period = int(getattr(self, 'slope_period', 10))
        self.slope_threshold = float(getattr(self, 'slope_threshold', 0.085))
        self.volatility_min = float(getattr(self, 'volatility_min', 0.15))
        self.exit_period = int(getattr(self, 'exit_period', 30))

        # 2. Local variables for parameters
        fast_macd = self.fast_macd
        slow_macd = self.slow_macd
        slope_period = self.slope_period
        slope_threshold = self.slope_threshold
        volatility_min = self.volatility_min
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        MACD_Hist = self.feat.macd(close, fastperiod=fast_macd, slowperiod=slow_macd, signalperiod=9)[2]
        Hist_Slope = self.feat.linearreg_slope(MACD_Hist, timeperiod=slope_period)
        NATR = self.feat.natr(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midpoint = self.feat.midpoint(close, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Hist_Slope > slope_threshold) & (NATR > volatility_min)
        short_setup = (Hist_Slope < -slope_threshold) & (NATR > volatility_min)

        # 6. Exit logic
        exit_long = (close < Midpoint - 0.25 * ATR) | (Hist_Slope < 0.0)
        exit_short = (close > Midpoint + 0.25 * ATR) | (Hist_Slope > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
