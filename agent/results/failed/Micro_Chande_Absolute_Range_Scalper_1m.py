from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.cmo_period = int(getattr(self, 'cmo_period', 8))
        self.cmo_trigger = float(getattr(self, 'cmo_trigger', 27.5))
        self.vol_factor = float(getattr(self, 'vol_factor', 1.2))
        self.exit_period = int(getattr(self, 'exit_period', 4))

        # 2. Local variables for parameters
        cmo_period = self.cmo_period
        cmo_trigger = self.cmo_trigger
        vol_factor = self.vol_factor
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        CMO = self.feat.cmo(close, timeperiod=cmo_period)
        TR = self.feat.trange(high, low, close)
        Noise_Floor = self.feat.stddev(close, timeperiod=10)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (CMO > cmo_trigger) & (TR > Noise_Floor * vol_factor)
        short_setup = (CMO < -cmo_trigger) & (TR > Noise_Floor * vol_factor)

        # 6. Exit logic
        exit_long = (CMO < 0.0) | (close < Micro_Low)
        exit_short = (CMO > 0.0) | (close > Micro_High)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
