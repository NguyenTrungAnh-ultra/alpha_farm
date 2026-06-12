from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.adx_period = int(getattr(self, 'adx_period', 10))
        self.adx_threshold = float(getattr(self, 'adx_threshold', 20.5))
        self.ema_period = int(getattr(self, 'ema_period', 22))
        self.atr_period = int(getattr(self, 'atr_period', 12))
        self.kc_mult = float(getattr(self, 'kc_mult', 1.2))
        self.exit_period = int(getattr(self, 'exit_period', 6))
        self.exit_mult = float(getattr(self, 'exit_mult', 3.7))

        # 2. Local variables for parameters
        adx_period = self.adx_period
        adx_threshold = self.adx_threshold
        ema_period = self.ema_period
        atr_period = self.atr_period
        kc_mult = self.kc_mult
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        ADX = self.feat.adx(high, low, close, timeperiod=adx_period)
        EMA_mid = self.feat.ema(close, timeperiod=ema_period)
        ATR = self.feat.atr(high, low, close, timeperiod=atr_period)
        Upper_Band = EMA_mid + (kc_mult * ATR)
        Lower_Band = EMA_mid - (kc_mult * ATR)
        Highest_High = self.feat.max(high, timeperiod=exit_period)
        Lowest_Low = self.feat.min(low, timeperiod=exit_period)
        Long_Trailing_Stop = Highest_High - (exit_mult * ATR)
        Short_Trailing_Stop = Lowest_Low + (exit_mult * ATR)

        # 5. Entry logic
        long_setup = (ADX > adx_threshold) & (close > Upper_Band)
        short_setup = (ADX > adx_threshold) & (close < Lower_Band)

        # 6. Exit logic
        exit_long = (close < Long_Trailing_Stop) | (close < EMA_mid)
        exit_short = (close > Short_Trailing_Stop) | (close > EMA_mid)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
