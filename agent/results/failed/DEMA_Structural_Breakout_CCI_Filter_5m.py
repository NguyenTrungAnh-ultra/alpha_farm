from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.dema_period = int(getattr(self, 'dema_period', 28))
        self.cci_period = int(getattr(self, 'cci_period', 20))
        self.cci_bound = float(getattr(self, 'cci_bound', 120.0))
        self.adx_min = float(getattr(self, 'adx_min', 21.0))
        self.channel_period = int(getattr(self, 'channel_period', 12))
        
        # 2. Local variables for parameters
        dema_period = self.dema_period
        cci_period = self.cci_period
        cci_bound = self.cci_bound
        adx_min = self.adx_min
        channel_period = self.channel_period
        
        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume
        
        # 4. Indicators
        DEMA = self.feat.dema(close, timeperiod=dema_period)
        CCI = self.feat.cci(high, low, close, timeperiod=cci_period)
        ADX = self.feat.adx(high, low, close, timeperiod=14)
        Channel_High = self.feat.max(high, timeperiod=channel_period)
        Channel_Low = self.feat.min(low, timeperiod=channel_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        
        # 5. Entry logic
        long_setup = (close > Channel_High) & (CCI > cci_bound) & (ADX > adx_min) & (close > DEMA)
        short_setup = (close < Channel_Low) & (CCI < -cci_bound) & (ADX > adx_min) & (close < DEMA)
        
        # 6. Exit logic
        exit_long = (close < DEMA - 0.5 * ATR) | (CCI < 0.0)
        exit_short = (close > DEMA + 0.5 * ATR) | (CCI > 0.0)
        exit_setup = exit_long | exit_short
        
        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
