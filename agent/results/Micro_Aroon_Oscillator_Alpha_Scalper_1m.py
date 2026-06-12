from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.aroon_period = int(getattr(self, 'aroon_period', 6))
        self.aroon_trigger = float(getattr(self, 'aroon_trigger', 20.0))
        self.expansion_mult = float(getattr(self, 'expansion_mult', 1.25))
        self.exit_period = int(getattr(self, 'exit_period', 3))

        # 2. Local variables for parameters
        aroon_period = self.aroon_period
        aroon_trigger = self.aroon_trigger
        expansion_mult = self.expansion_mult
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Aroon_Osc = self.feat.aroonosc(high, low, timeperiod=aroon_period)
        Volatility_Fast = self.feat.stddev(close, timeperiod=8)
        Volatility_Base = self.feat.sma(Volatility_Fast, timeperiod=25)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Aroon_Osc > aroon_trigger) & (Volatility_Fast > Volatility_Base * expansion_mult)
        short_setup = (Aroon_Osc < -aroon_trigger) & (Volatility_Fast > Volatility_Base * expansion_mult)

        # 6. Exit logic
        exit_long = (close < Micro_Low) | (Aroon_Osc < 0.0)
        exit_short = (close > Micro_High) | (Aroon_Osc > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
