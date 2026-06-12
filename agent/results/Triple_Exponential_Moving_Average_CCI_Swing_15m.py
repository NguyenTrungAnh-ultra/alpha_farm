from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.tema_period = int(getattr(self, 'tema_period', 40))
        self.cci_period = int(getattr(self, 'cci_period', 12))
        self.cci_bound = float(getattr(self, 'cci_bound', 70.0))
        self.expansion_mult = float(getattr(self, 'expansion_mult', 1.05))
        self.exit_period = int(getattr(self, 'exit_period', 13))
        self.exit_mult = float(getattr(self, 'exit_mult', 2.7))

        # 2. Local variables for parameters
        tema_period = self.tema_period
        cci_period = self.cci_period
        cci_bound = self.cci_bound
        expansion_mult = self.expansion_mult
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        TEMA = self.feat.tema(close, timeperiod=tema_period)
        CCI_Raw = self.feat.cci(high, low, close, timeperiod=cci_period)
        CCI_Smooth = self.feat.wma(CCI_Raw, timeperiod=5)
        Volatility_Fast = self.feat.stddev(close, timeperiod=10)
        Volatility_Base = self.feat.sma(Volatility_Fast, timeperiod=30)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > TEMA) & (CCI_Smooth > cci_bound) & (Volatility_Fast > Volatility_Base * expansion_mult)
        short_setup = (close < TEMA) & (CCI_Smooth < -cci_bound) & (Volatility_Fast > Volatility_Base * expansion_mult)

        # 6. Exit logic
        exit_long = (close < TEMA) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (close > TEMA) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
