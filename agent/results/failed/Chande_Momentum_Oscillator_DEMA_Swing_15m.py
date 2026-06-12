from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.dema_period = int(getattr(self, 'dema_period', 23))
        self.slope_threshold = float(getattr(self, 'slope_threshold', 0.3))
        self.cmo_period = int(getattr(self, 'cmo_period', 13))
        self.cmo_trigger = float(getattr(self, 'cmo_trigger', 10.0))
        self.vol_factor = float(getattr(self, 'vol_factor', 1.5))
        self.exit_period = int(getattr(self, 'exit_period', 21))
        self.exit_mult = float(getattr(self, 'exit_mult', 2.9))
        
        # 2. Local variables for parameters
        dema_period = self.dema_period
        slope_threshold = self.slope_threshold
        cmo_period = self.cmo_period
        cmo_trigger = self.cmo_trigger
        vol_factor = self.vol_factor
        exit_period = self.exit_period
        exit_mult = self.exit_mult
        
        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume
        
        # 4. Indicators
        DEMA_Fast = self.feat.dema(close, timeperiod=dema_period)
        DEMA_Slope = self.feat.linearreg_slope(DEMA_Fast, timeperiod=5)
        CMO = self.feat.cmo(close, timeperiod=cmo_period)
        TR = self.feat.trange(high, low, close)
        ATR_Filter = self.feat.atr(high, low, close, timeperiod=30)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)
        
        # 5. Entry logic
        long_setup = (DEMA_Slope > slope_threshold) & (CMO > cmo_trigger) & (TR > ATR_Filter * vol_factor)
        short_setup = (DEMA_Slope < -slope_threshold) & (CMO < -cmo_trigger) & (TR > ATR_Filter * vol_factor)
        
        # 6. Exit logic
        exit_long = (close < Rolling_Max - (exit_mult * ATR)) | (CMO < 0.0)
        exit_short = (close > Rolling_Min + (exit_mult * ATR)) | (CMO > 0.0)
        exit_setup = exit_long | exit_short
        
        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
