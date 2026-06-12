from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.stoch_period = int(getattr(self, 'stoch_period', 11))
        self.dx_period = int(getattr(self, 'dx_period', 12))
        self.dx_threshold = float(getattr(self, 'dx_threshold', 30.0))
        self.noise_floor = float(getattr(self, 'noise_floor', 0.8))
        self.exit_period = int(getattr(self, 'exit_period', 4))

        # 2. Local variables for parameters
        stoch_period = self.stoch_period
        dx_period = self.dx_period
        dx_threshold = self.dx_threshold
        noise_floor = self.noise_floor
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Stoch_K = self.feat.stochrsi(close, timeperiod=stoch_period, fastk_period=5, fastd_period=3, fastd_matype=0)[0]
        Stoch_D = self.feat.stochrsi(close, timeperiod=stoch_period, fastk_period=5, fastd_period=3, fastd_matype=0)[1]
        DX = self.feat.dx(high, low, close, timeperiod=dx_period)
        Noise_Filter = self.feat.stddev(close, timeperiod=10)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Stoch_K > Stoch_D) & (Stoch_K < 30.0) & (DX > dx_threshold) & (Noise_Filter > noise_floor)
        short_setup = (Stoch_K < Stoch_D) & (Stoch_K > 70.0) & (DX > dx_threshold) & (Noise_Filter > noise_floor)

        # 6. Exit logic
        exit_long = (Stoch_K < Stoch_D) | (close < Micro_Low)
        exit_short = (Stoch_K > Stoch_D) | (close > Micro_High)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
