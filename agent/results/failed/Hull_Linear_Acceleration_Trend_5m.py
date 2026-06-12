from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.wma_period = int(getattr(self, 'wma_period', 26))
        self.slope_period = int(getattr(self, 'slope_period', 20))
        self.slope_trigger = float(getattr(self, 'slope_trigger', 0.05))
        self.noise_threshold = float(getattr(self, 'noise_threshold', 1.7000000000000002))
        self.exit_period = int(getattr(self, 'exit_period', 8))
        
        # 2. Local variables for parameters
        wma_period = self.wma_period
        slope_period = self.slope_period
        slope_trigger = self.slope_trigger
        noise_threshold = self.noise_threshold
        exit_period = self.exit_period
        
        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume
        
        # 4. Indicators
        WMA_Trend = self.feat.wma(close, timeperiod=wma_period)
        L_Slope = self.feat.linearreg_slope(close, timeperiod=slope_period)
        StdDev = self.feat.stddev(close, timeperiod=wma_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midprice_Exit = self.feat.midprice(high, low, timeperiod=exit_period)
        
        # 5. Entry logic
        long_setup = (close > WMA_Trend) & (L_Slope > slope_trigger) & (StdDev > noise_threshold)
        short_setup = (close < WMA_Trend) & (L_Slope < -slope_trigger) & (StdDev > noise_threshold)
        
        # 6. Exit logic
        exit_long = (close < Midprice_Exit - 0.25 * ATR) | (L_Slope < 0.0)
        exit_short = (close > Midprice_Exit + 0.25 * ATR) | (L_Slope > 0.0)
        exit_setup = exit_long | exit_short
        
        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
