from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.smooth_period = int(getattr(self, 'smooth_period', 10))
        self.angle_period = int(getattr(self, 'angle_period', 14))
        self.bop_threshold = float(getattr(self, 'bop_threshold', 0.05))
        self.angle_threshold = float(getattr(self, 'angle_threshold', 20.0))
        self.exit_period = int(getattr(self, 'exit_period', 13))
        self.exit_mult = float(getattr(self, 'exit_mult', 2.8))

        # 2. Local variables for parameters
        smooth_period = self.smooth_period
        angle_period = self.angle_period
        bop_threshold = self.bop_threshold
        angle_threshold = self.angle_threshold
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        BOP = self.feat.bop(open, high, low, close)
        BOP_Smooth = self.feat.sma(BOP, timeperiod=smooth_period)
        LR_Angle = self.feat.linearreg_angle(close, timeperiod=angle_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (BOP_Smooth > bop_threshold) & (LR_Angle > angle_threshold)
        short_setup = (BOP_Smooth < -bop_threshold) & (LR_Angle < -angle_threshold)

        # 6. Exit logic
        exit_long = (close < Rolling_Max - (exit_mult * ATR)) | (LR_Angle < 0.0)
        exit_short = (close > Rolling_Min + (exit_mult * ATR)) | (LR_Angle > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
