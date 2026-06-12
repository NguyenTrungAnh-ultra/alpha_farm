from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.fast_apo = int(getattr(self, 'fast_apo', 13))
        self.slow_apo = int(getattr(self, 'slow_apo', 38))
        self.apo_threshold = float(getattr(self, 'apo_threshold', 0.5))
        self.sar_acc = float(getattr(self, 'sar_acc', 0.03))
        self.sar_max = float(getattr(self, 'sar_max', 0.14))
        self.natr_min = float(getattr(self, 'natr_min', 0.08))
        self.exit_period = int(getattr(self, 'exit_period', 10))
        self.exit_mult = float(getattr(self, 'exit_mult', 2.9))
        
        # 2. Local variables for parameters
        fast_apo = self.fast_apo
        slow_apo = self.slow_apo
        apo_threshold = self.apo_threshold
        sar_acc = self.sar_acc
        sar_max = self.sar_max
        natr_min = self.natr_min
        exit_period = self.exit_period
        exit_mult = self.exit_mult
        
        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume
        
        # 4. Indicators
        APO = self.feat.apo(close, fastperiod=fast_apo, slowperiod=slow_apo, matype=1)
        SAR = self.feat.sar(high, low, acceleration=sar_acc, maximum=sar_max)
        NATR = self.feat.natr(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)
        
        # 5. Entry logic
        long_setup = (APO > apo_threshold) & (close > SAR) & (NATR > natr_min)
        short_setup = (APO < -apo_threshold) & (close < SAR) & (NATR > natr_min)
        
        # 6. Exit logic
        exit_long = (close < SAR) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (close > SAR) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short
        
        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
