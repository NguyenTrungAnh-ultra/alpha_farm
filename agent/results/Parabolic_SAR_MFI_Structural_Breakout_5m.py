from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.sar_acc = float(getattr(self, 'sar_acc', 0.02))
        self.sar_max = float(getattr(self, 'sar_max', 0.18))
        self.mfi_period = int(getattr(self, 'mfi_period', 24))
        self.mfi_offset = float(getattr(self, 'mfi_offset', 9.0))
        self.exit_period = int(getattr(self, 'exit_period', 17))
        self.exit_mult = float(getattr(self, 'exit_mult', 1.9))

        # 2. Local variables for parameters
        sar_acc = self.sar_acc
        sar_max = self.sar_max
        mfi_period = self.mfi_period
        mfi_offset = self.mfi_offset
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        SAR = self.feat.sar(high, low, acceleration=sar_acc, maximum=sar_max)
        MFI = self.feat.mfi(high, low, close, volume, timeperiod=mfi_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > SAR) & (MFI > 50.0 + mfi_offset)
        short_setup = (close < SAR) & (MFI < 50.0 - mfi_offset)

        # 6. Exit logic
        exit_long = (close < SAR) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (close > SAR) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
