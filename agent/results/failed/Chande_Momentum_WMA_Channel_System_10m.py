from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.wma_period = int(getattr(self, 'wma_period', 28))
        self.cmo_period = int(getattr(self, 'cmo_period', 14))
        self.cmo_trigger = float(getattr(self, 'cmo_trigger', 25.0))
        self.vol_floor = float(getattr(self, 'vol_floor', 0.75))
        self.exit_period = int(getattr(self, 'exit_period', 13))
        self.exit_mult = float(getattr(self, 'exit_mult', 2.0))
        
        # 2. Local variables for parameters
        wma_period = self.wma_period
        cmo_period = self.cmo_period
        cmo_trigger = self.cmo_trigger
        vol_floor = self.vol_floor
        exit_period = self.exit_period
        exit_mult = self.exit_mult
        
        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume
        
        # 4. Indicators
        WMA_Center = self.feat.wma(close, timeperiod=wma_period)
        CMO = self.feat.cmo(close, timeperiod=cmo_period)
        TR = self.feat.trange(high, low, close)
        ATR_Baseline = self.feat.atr(high, low, close, timeperiod=30)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)
        
        # 5. Entry logic
        long_setup = (close > WMA_Center) & (CMO > cmo_trigger) & (TR > ATR_Baseline * vol_floor)
        short_setup = (close < WMA_Center) & (CMO < -cmo_trigger) & (TR > ATR_Baseline * vol_floor)
        
        # 6. Exit logic
        exit_long = (close < WMA_Center) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (close > WMA_Center) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short
        
        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
