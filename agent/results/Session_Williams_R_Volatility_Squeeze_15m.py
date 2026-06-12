from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.trima_period = int(getattr(self, 'trima_period', 26))
        self.willr_period = int(getattr(self, 'willr_period', 16))
        self.squeeze_factor = float(getattr(self, 'squeeze_factor', 0.65))
        self.exit_period = int(getattr(self, 'exit_period', 24))

        # 2. Local variables for parameters
        trima_period = self.trima_period
        willr_period = self.willr_period
        squeeze_factor = self.squeeze_factor
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        TRIMA = self.feat.trima(close, timeperiod=trima_period)
        WILLR = self.feat.willr(high, low, close, timeperiod=willr_period)
        StdDev_Fast = self.feat.stddev(close, timeperiod=10)
        ATR = self.feat.atr(high, low, close, timeperiod=20)
        Midpoint_Exit = self.feat.midpoint(close, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > TRIMA) & (WILLR > -30.0) & (StdDev_Fast > ATR * squeeze_factor)
        short_setup = (close < TRIMA) & (WILLR < -70.0) & (StdDev_Fast > ATR * squeeze_factor)

        # 6. Exit logic
        exit_long = (close < Midpoint_Exit) | (WILLR < -50.0)
        exit_short = (close > Midpoint_Exit) | (WILLR > -50.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
