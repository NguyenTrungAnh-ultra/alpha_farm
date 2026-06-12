from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.slope_period = int(getattr(self, 'slope_period', 24))
        self.slope_threshold = float(getattr(self, 'slope_threshold', 0.05))
        self.cmo_period = int(getattr(self, 'cmo_period', 10))
        self.cmo_long_trigger = float(getattr(self, 'cmo_long_trigger', 25.0))
        self.cmo_short_trigger = float(getattr(self, 'cmo_short_trigger', -25.0))
        self.dc_period = int(getattr(self, 'dc_period', 18))

        # 2. Local variables for parameters
        slope_period = self.slope_period
        slope_threshold = self.slope_threshold
        cmo_period = self.cmo_period
        cmo_long_trigger = self.cmo_long_trigger
        cmo_short_trigger = self.cmo_short_trigger
        dc_period = self.dc_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Slope = self.feat.linearreg_slope(close, timeperiod=slope_period)
        CMO = self.feat.cmo(close, timeperiod=cmo_period)
        Donchian_High = self.feat.max(high, timeperiod=dc_period)
        Donchian_Low = self.feat.min(low, timeperiod=dc_period)
        Donchian_Mid = (Donchian_High + Donchian_Low) / 2.0

        # 5. Entry logic
        long_setup = (Slope > slope_threshold) & (CMO > cmo_long_trigger)
        short_setup = (Slope < -slope_threshold) & (CMO < cmo_short_trigger)

        # 6. Exit logic
        exit_long = (close < Donchian_Mid)
        exit_short = (close > Donchian_Mid)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
