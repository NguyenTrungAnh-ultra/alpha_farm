from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.wma_period = int(getattr(self, 'wma_period', 44))
        self.channel_mult = float(getattr(self, 'channel_mult', 1.2))
        self.roc_period = int(getattr(self, 'roc_period', 21))
        self.roc_threshold = float(getattr(self, 'roc_threshold', 0.25))
        self.exit_period = int(getattr(self, 'exit_period', 15))
        self.exit_mult = float(getattr(self, 'exit_mult', 2.5))

        # 2. Local variables for parameters
        wma_period = self.wma_period
        channel_mult = self.channel_mult
        roc_period = self.roc_period
        roc_threshold = self.roc_threshold
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        WMA_Baseline = self.feat.wma(close, timeperiod=wma_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Upper_Band = WMA_Baseline + (channel_mult * ATR)
        Lower_Band = WMA_Baseline - (channel_mult * ATR)
        ROC = self.feat.roc(close, timeperiod=roc_period)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > Upper_Band) & (ROC > roc_threshold)
        short_setup = (close < Lower_Band) & (ROC < -roc_threshold)

        # 6. Exit logic
        exit_long = (close < WMA_Baseline) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (close > WMA_Baseline) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
