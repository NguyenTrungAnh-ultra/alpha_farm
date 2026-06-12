from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.t3_period = int(getattr(self, 't3_period', 20))
        self.deviation_mult = float(getattr(self, 'deviation_mult', 2.0))
        self.dx_min = float(getattr(self, 'dx_min', 21.0))

        # 2. Local variables for parameters
        t3_period = self.t3_period
        deviation_mult = self.deviation_mult
        dx_min = self.dx_min

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        T3_Base = self.feat.t3(close, timeperiod=t3_period, vfactor=0.7)
        TR_Smooth = self.feat.wma(self.feat.trange(high, low, close), timeperiod=14)
        Upper_Target = T3_Base + (deviation_mult * TR_Smooth)
        Lower_Target = T3_Base - (deviation_mult * TR_Smooth)
        DX = self.feat.dx(high, low, close, timeperiod=10)
        ATR = self.feat.atr(high, low, close, timeperiod=14)

        # 5. Entry logic
        long_setup = (close < Lower_Target) & (DX > dx_min)
        short_setup = (close > Upper_Target) & (DX > dx_min)

        # 6. Exit logic
        exit_long = (close > T3_Base) | (close < Lower_Target - 0.5 * ATR)
        exit_short = (close < T3_Base) | (close > Upper_Target + 0.5 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
