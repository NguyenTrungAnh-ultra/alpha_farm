from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.aroon_period = int(getattr(self, 'aroon_period', 27))
        self.aroon_threshold = float(getattr(self, 'aroon_threshold', 50.0))
        self.bb_period = int(getattr(self, 'bb_period', 22))
        self.bb_mult = float(getattr(self, 'bb_mult', 2.1))
        self.width_min = float(getattr(self, 'width_min', 0.01))
        self.exit_period = int(getattr(self, 'exit_period', 15))
        self.exit_mult = float(getattr(self, 'exit_mult', 3.25))

        # 2. Local variables for parameters
        aroon_period = self.aroon_period
        aroon_threshold = self.aroon_threshold
        bb_period = self.bb_period
        bb_mult = self.bb_mult
        width_min = self.width_min
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Aroon_Osc = self.feat.aroonosc(high, low, timeperiod=aroon_period)
        BB_Upper = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_mult, nbdevdn=bb_mult)[0]
        BB_Lower = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_mult, nbdevdn=bb_mult)[2]
        BB_Width = (BB_Upper - BB_Lower) / (self.feat.midpoint(close, timeperiod=bb_period) + 1e-8)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Aroon_Osc > aroon_threshold) & (BB_Width > width_min) & (close > BB_Upper)
        short_setup = (Aroon_Osc < -aroon_threshold) & (BB_Width > width_min) & (close < BB_Lower)

        # 6. Exit logic
        exit_long = (close < Rolling_Max - (exit_mult * ATR)) | (Aroon_Osc < 0.0)
        exit_short = (close > Rolling_Min + (exit_mult * ATR)) | (Aroon_Osc > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
