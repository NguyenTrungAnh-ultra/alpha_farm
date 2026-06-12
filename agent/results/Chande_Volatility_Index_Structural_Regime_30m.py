from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.tema_period = int(getattr(self, 'tema_period', 45))
        self.cmo_period = int(getattr(self, 'cmo_period', 21))
        self.cmo_threshold = float(getattr(self, 'cmo_threshold', 20.0))
        self.expansion_mult = float(getattr(self, 'expansion_mult', 1.3))
        self.exit_period = int(getattr(self, 'exit_period', 24))

        # 2. Local variables for parameters
        tema_period = self.tema_period
        cmo_period = self.cmo_period
        cmo_threshold = self.cmo_threshold
        expansion_mult = self.expansion_mult
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        TEMA_Basis = self.feat.tema(close, timeperiod=tema_period)
        CMO = self.feat.cmo(close, timeperiod=cmo_period)
        Volatility_Fast = self.feat.stddev(close, timeperiod=10)
        Volatility_Baseline = self.feat.midpoint(Volatility_Fast, timeperiod=30)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midprice_Exit = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > TEMA_Basis) & (CMO > cmo_threshold) & (Volatility_Fast > Volatility_Baseline * expansion_mult)
        short_setup = (close < TEMA_Basis) & (CMO < -cmo_threshold) & (Volatility_Fast > Volatility_Baseline * expansion_mult)

        # 6. Exit logic
        exit_long = (close < Midprice_Exit - 0.5 * ATR) | (CMO < 0.0)
        exit_short = (close > Midprice_Exit + 0.5 * ATR) | (CMO > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
