from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.trix_period = int(getattr(self, 'trix_period', 5))
        self.trix_trigger = float(getattr(self, 'trix_trigger', 0.008))
        self.noise_floor = float(getattr(self, 'noise_floor', 0.75))
        self.exit_period = int(getattr(self, 'exit_period', 4))

        # 2. Local variables for parameters
        trix_period = self.trix_period
        trix_trigger = self.trix_trigger
        noise_floor = self.noise_floor
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        TRIX = self.feat.trix(close, timeperiod=trix_period)
        CCI = self.feat.cci(high, low, close, timeperiod=7)
        StdDev_Filter = self.feat.stddev(close, timeperiod=10)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (TRIX > trix_trigger) & (StdDev_Filter > noise_floor)
        short_setup = (TRIX < -trix_trigger) & (StdDev_Filter > noise_floor)

        # 6. Exit logic
        exit_long = (CCI < -100.0) | (close < Micro_Low)
        exit_short = (CCI > 100.0) | (close > Micro_High)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
