from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.tema_period = int(getattr(self, 'tema_period', 15))
        self.atr_period = int(getattr(self, 'atr_period', 27))
        self.channel_mult = float(getattr(self, 'channel_mult', 1.2))
        self.vol_min = float(getattr(self, 'vol_min', 0.002))
        self.exit_period = int(getattr(self, 'exit_period', 20))

        # 2. Local variables for parameters
        tema_period = self.tema_period
        atr_period = self.atr_period
        channel_mult = self.channel_mult
        vol_min = self.vol_min
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        TEMA_Basis = self.feat.t3(close, timeperiod=tema_period)
        ATR = self.feat.atr(high, low, close, timeperiod=atr_period)
        Upper_Channel = TEMA_Basis + (channel_mult * ATR)
        Lower_Channel = TEMA_Basis - (channel_mult * ATR)
        Normalized_StdDev = self.feat.stddev(close, timeperiod=20) / (self.feat.midprice(high, low, timeperiod=20) + 1e-8)
        Dynamic_Mid = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (Normalized_StdDev > vol_min) & (close > Upper_Channel)
        short_setup = (Normalized_StdDev > vol_min) & (close < Lower_Channel)

        # 6. Exit logic
        exit_long = (close < Dynamic_Mid - 0.5 * ATR)
        exit_short = (close > Dynamic_Mid + 0.5 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
