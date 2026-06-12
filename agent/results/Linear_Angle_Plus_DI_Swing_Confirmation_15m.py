from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.angle_period = int(getattr(self, 'angle_period', 14))
        self.angle_threshold = float(getattr(self, 'angle_threshold', 15.0))
        self.di_period = int(getattr(self, 'di_period', 24))
        self.natr_min = float(getattr(self, 'natr_min', 0.05))
        self.exit_period = int(getattr(self, 'exit_period', 26))

        # 2. Local variables for parameters
        angle_period = self.angle_period
        angle_threshold = self.angle_threshold
        di_period = self.di_period
        natr_min = self.natr_min
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        LR_Angle = self.feat.linearreg_angle(close, timeperiod=angle_period)
        Plus_DI = self.feat.plus_di(high, low, close, timeperiod=di_period)
        Minus_DI = self.feat.minus_di(high, low, close, timeperiod=di_period)
        NATR = self.feat.natr(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midpoint = self.feat.midpoint(close, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (LR_Angle > angle_threshold) & (Plus_DI > Minus_DI) & (NATR > natr_min)
        short_setup = (LR_Angle < -angle_threshold) & (Minus_DI > Plus_DI) & (NATR > natr_min)

        # 6. Exit logic
        exit_long = (close < Midpoint - 0.5 * ATR) | (LR_Angle < 0.0)
        exit_short = (close > Midpoint + 0.25 * ATR) | (LR_Angle > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
