from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.cci_period = int(getattr(self, 'cci_period', 17))
        self.cci_long_bound = float(getattr(self, 'cci_long_bound', 0.0))
        self.cci_short_bound = float(getattr(self, 'cci_short_bound', 0.0))
        self.natr_period = int(getattr(self, 'natr_period', 15))
        self.natr_threshold = float(getattr(self, 'natr_threshold', 0.15))
        self.lr_period = int(getattr(self, 'lr_period', 22))

        # 2. Local variables for parameters
        cci_period = self.cci_period
        cci_long_bound = self.cci_long_bound
        cci_short_bound = self.cci_short_bound
        natr_period = self.natr_period
        natr_threshold = self.natr_threshold
        lr_period = self.lr_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Engulfing = self.feat.cdlengulfing(open, high, low, close)
        CCI = self.feat.cci(high, low, close, timeperiod=cci_period)
        NATR = self.feat.natr(high, low, close, timeperiod=natr_period)
        LR_Center = self.feat.linearreg(close, timeperiod=lr_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)

        # 5. Entry logic
        long_setup = (Engulfing > 0) & (CCI > cci_long_bound) & (NATR > natr_threshold)
        short_setup = (Engulfing < 0) & (CCI < cci_short_bound) & (NATR > natr_threshold)

        # 6. Exit logic
        exit_long = (close < LR_Center - 0.5 * ATR)
        exit_short = (close > LR_Center + 0.5 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
