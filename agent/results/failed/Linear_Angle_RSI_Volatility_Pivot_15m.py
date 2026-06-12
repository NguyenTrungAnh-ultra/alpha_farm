from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.angle_period = int(getattr(self, 'angle_period', 32))
        self.angle_min = float(getattr(self, 'angle_min', 22.5))
        self.rsi_period = int(getattr(self, 'rsi_period', 16))
        self.natr_threshold = float(getattr(self, 'natr_threshold', 0.11))
        self.exit_period = int(getattr(self, 'exit_period', 19))

        # 2. Local variables for parameters
        angle_period = self.angle_period
        angle_min = self.angle_min
        rsi_period = self.rsi_period
        natr_threshold = self.natr_threshold
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        LR_Angle = self.feat.linearreg_angle(close, timeperiod=angle_period)
        RSI = self.feat.rsi(close, timeperiod=rsi_period)
        NATR = self.feat.natr(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midpoint_Exit = self.feat.midpoint(close, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (LR_Angle > angle_min) & (RSI > 50.0) & (NATR > natr_threshold)
        short_setup = (LR_Angle < -angle_min) & (RSI < 50.0) & (NATR > natr_threshold)

        # 6. Exit logic
        exit_long = (close < Midpoint_Exit - 0.5 * ATR) | (LR_Angle < 0.0)
        exit_short = (close > Midpoint_Exit + 0.5 * ATR) | (LR_Angle > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
