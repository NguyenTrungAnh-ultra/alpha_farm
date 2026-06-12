from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.kama_period = int(getattr(self, 'kama_period', 8))
        self.slope_threshold = float(getattr(self, 'slope_threshold', 0.1))
        self.bop_threshold = float(getattr(self, 'bop_threshold', 0.15))
        self.noise_floor = float(getattr(self, 'noise_floor', 0.65))
        self.exit_period = int(getattr(self, 'exit_period', 4))

        # 2. Local variables for parameters
        kama_period = self.kama_period
        slope_threshold = self.slope_threshold
        bop_threshold = self.bop_threshold
        noise_floor = self.noise_floor
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Fast_KAMA = self.feat.kama(close, timeperiod=kama_period)
        KAMA_Slope = self.feat.linearreg_slope(Fast_KAMA, timeperiod=3)
        BOP = self.feat.bop(open, high, low, close)
        BOP_Smooth = self.feat.wma(BOP, timeperiod=5)
        Volatility_Filter = self.feat.stddev(close, timeperiod=10)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (KAMA_Slope > slope_threshold) & (BOP_Smooth > bop_threshold) & (Volatility_Filter > noise_floor)
        short_setup = (KAMA_Slope < -slope_threshold) & (BOP_Smooth < -bop_threshold) & (Volatility_Filter > noise_floor)

        # 6. Exit logic
        exit_long = (close < Micro_Low) | (KAMA_Slope < 0.0)
        exit_short = (close > Micro_High) | (KAMA_Slope > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
