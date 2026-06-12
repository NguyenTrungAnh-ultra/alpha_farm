from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.trend_period = int(getattr(self, 'trend_period', 40))
        self.mfi_period = int(getattr(self, 'mfi_period', 15))
        self.mfi_oversold = float(getattr(self, 'mfi_oversold', 30.0))
        self.mfi_overbought = float(getattr(self, 'mfi_overbought', 70.0))
        self.di_period = int(getattr(self, 'di_period', 14))
        self.exit_period = int(getattr(self, 'exit_period', 15))

        # 2. Local variables for parameters
        trend_period = self.trend_period
        mfi_period = self.mfi_period
        mfi_oversold = self.mfi_oversold
        mfi_overbought = self.mfi_overbought
        di_period = self.di_period
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Macro_Trend = self.feat.trima(close, timeperiod=trend_period)
        MFI = self.feat.mfi(high, low, close, volume, timeperiod=mfi_period)
        Plus_DI = self.feat.plus_di(high, low, close, timeperiod=di_period)
        Minus_DI = self.feat.minus_di(high, low, close, timeperiod=di_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Exit_Anchor = self.feat.midpoint(close, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > Macro_Trend) & (MFI < mfi_oversold) & (Plus_DI > Minus_DI)
        short_setup = (close < Macro_Trend) & (MFI > mfi_overbought) & (Minus_DI > Plus_DI)

        # 6. Exit logic
        exit_long = (close < Exit_Anchor - 0.5 * ATR)
        exit_short = (close > Exit_Anchor + 0.5 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
