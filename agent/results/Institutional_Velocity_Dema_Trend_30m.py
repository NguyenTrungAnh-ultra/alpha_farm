from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.dema_period = int(getattr(self, 'dema_period', 32))
        self.mom_period = int(getattr(self, 'mom_period', 25))
        self.mom_threshold = float(getattr(self, 'mom_threshold', 3.0))
        self.adxr_period = int(getattr(self, 'adxr_period', 20))
        self.adxr_min = float(getattr(self, 'adxr_min', 15.0))
        self.exit_period = int(getattr(self, 'exit_period', 28))
        
        # 2. Local variables for parameters
        dema_period = self.dema_period
        mom_period = self.mom_period
        mom_threshold = self.mom_threshold
        adxr_period = self.adxr_period
        adxr_min = self.adxr_min
        exit_period = self.exit_period
        
        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume
        
        # 4. Indicators
        DEMA = self.feat.dema(close, timeperiod=dema_period)
        MOM = self.feat.mom(close, timeperiod=mom_period)
        ADXR = self.feat.adxr(high, low, close, timeperiod=adxr_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midprice_Exit = self.feat.midprice(high, low, timeperiod=exit_period)
        
        # 5. Entry logic
        long_setup = (close > DEMA) & (MOM > mom_threshold) & (ADXR > adxr_min)
        short_setup = (close < DEMA) & (MOM < -mom_threshold) & (ADXR > adxr_min)
        
        # 6. Exit logic
        exit_long = (close < Midprice_Exit - 0.5 * ATR) | (MOM < 0.0)
        exit_short = (close > Midprice_Exit + 0.5 * ATR) | (MOM > 0.0)
        exit_setup = exit_long | exit_short
        
        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
