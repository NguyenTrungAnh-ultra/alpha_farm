from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.atr_period = int(getattr(self, 'atr_period', 12))
        self.vol_trigger = float(getattr(self, 'vol_trigger', 1.45))
        self.trend_period = int(getattr(self, 'trend_period', 11))
        self.angle_threshold = float(getattr(self, 'angle_threshold', 15.0))
        self.exit_period = int(getattr(self, 'exit_period', 4))

        # 2. Local variables for parameters
        atr_period = self.atr_period
        vol_trigger = self.vol_trigger
        trend_period = self.trend_period
        angle_threshold = self.angle_threshold
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        TR = self.feat.trange(high, low, close)
        Micro_ATR = self.feat.atr(high, low, close, timeperiod=atr_period)
        Vol_Ratio = TR / (Micro_ATR + 1e-8)
        LR_Angle = self.feat.linearreg_angle(close, timeperiod=trend_period)
        ROCP = self.feat.rocp(close, timeperiod=3)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Vol_Ratio > vol_trigger) & (LR_Angle > angle_threshold) & (ROCP > 0.0005)
        short_setup = (Vol_Ratio > vol_trigger) & (LR_Angle < -angle_threshold) & (ROCP < -0.0005)

        # 6. Exit logic
        exit_long = (close < Micro_Low) | (LR_Angle < 0.0)
        exit_short = (close > Micro_High) | (LR_Angle > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
