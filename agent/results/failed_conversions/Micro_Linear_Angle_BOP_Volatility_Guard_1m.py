from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.angle_period = int(getattr(self, 'angle_period', 8))
        self.angle_trigger = float(getattr(self, 'angle_trigger', 30.0))
        self.bop_min = float(getattr(self, 'bop_min', 0.15))
        self.expansion_ratio = float(getattr(self, 'expansion_ratio', 1.3))
        self.exit_period = int(getattr(self, 'exit_period', 4))

        # 2. Local variables for parameters
        angle_period = self.angle_period
        angle_trigger = self.angle_trigger
        bop_min = self.bop_min
        expansion_ratio = self.expansion_ratio
        exit_period = self.exit_period

        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume

        # 4. Indicators
        LR_Angle = self.feat.linearreg_angle(close, timeperiod=angle_period)
        BOP = self.feat.bop(open, high, low, close)
        BOP_Smooth = self.feat.wma(BOP, timeperiod=4)
        Volatility_Fast = self.feat.stddev(close, timeperiod=8)
        Volatility_Base = self.feat.sma(Volatility_Fast, timeperiod=24)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (LR_Angle > angle_trigger) & (BOP_Smooth > bop_min) & (Volatility_Fast > Volatility_Base * expansion_ratio)
        short_setup = (LR_Angle < -angle_trigger) & (BOP_Smooth < -bop_min) & (Volatility_Fast > Volatility_Base * expansion_ratio)

        # 6. Exit logic
        exit_long = (close < Micro_Low) | (LR_Angle < 0.0)
        exit_short = (close > Micro_High) | (LR_Angle > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
