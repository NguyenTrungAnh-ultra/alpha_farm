from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.kama_period = int(getattr(self, 'kama_period', 16))
        self.adx_min = float(getattr(self, 'adx_min', 23.5))
        self.exit_period = int(getattr(self, 'exit_period', 12))
        self.exit_mult = float(getattr(self, 'exit_mult', 1.6))

        # 2. Local variables for parameters
        kama_period = self.kama_period
        adx_min = self.adx_min
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        KAMA = self.feat.kama(close, timeperiod=kama_period)
        ADX = self.feat.adx(high, low, close, timeperiod=14)
        Plus_DI = self.feat.plus_di(high, low, close, timeperiod=14)
        Minus_DI = self.feat.minus_di(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > KAMA) & (ADX > adx_min) & (Plus_DI > Minus_DI)
        short_setup = (close < KAMA) & (ADX > adx_min) & (Minus_DI > Plus_DI)

        # 6. Exit logic
        exit_long = (close < KAMA) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (close > KAMA) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
