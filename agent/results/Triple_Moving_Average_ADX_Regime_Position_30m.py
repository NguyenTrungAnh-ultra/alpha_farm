from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.tema_period = int(getattr(self, 'tema_period', 26))
        self.adx_min = float(getattr(self, 'adx_min', 18.0))
        self.exit_period = int(getattr(self, 'exit_period', 25))

        # 2. Local variables for parameters
        tema_period = self.tema_period
        adx_min = self.adx_min
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        TEMA = self.feat.tema(close, timeperiod=tema_period)
        ADX = self.feat.adx(high, low, close, timeperiod=14)
        Plus_DI = self.feat.plus_di(high, low, close, timeperiod=14)
        Minus_DI = self.feat.minus_di(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Exit_Mid = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > TEMA) & (ADX > adx_min) & (Plus_DI > Minus_DI)
        short_setup = (close < TEMA) & (ADX > adx_min) & (Minus_DI > Plus_DI)

        # 6. Exit logic
        exit_long = (close < TEMA) | (close < Exit_Mid - 0.5 * ATR)
        exit_short = (close > TEMA) | (close > Exit_Mid + 0.5 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
