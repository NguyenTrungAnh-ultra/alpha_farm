from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.wma_period = int(getattr(self, 'wma_period', 30))
        self.stoch_period = int(getattr(self, 'stoch_period', 14))
        self.oversold_bound = float(getattr(self, 'oversold_bound', 32.5))
        self.overbought_bound = float(getattr(self, 'overbought_bound', 67.5))
        self.exit_period = int(getattr(self, 'exit_period', 12))
        self.exit_mult = float(getattr(self, 'exit_mult', 2.5))

        # 2. Local variables for parameters
        wma_period = self.wma_period
        stoch_period = self.stoch_period
        oversold_bound = self.oversold_bound
        overbought_bound = self.overbought_bound
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        WMA_Trend = self.feat.wma(close, timeperiod=wma_period)
        Stoch_K = self.feat.stochf(high, low, close, fastk_period=stoch_period, fastd_period=3, fastd_matype=0)[0]
        Stoch_D = self.feat.stochf(high, low, close, fastk_period=stoch_period, fastd_period=3, fastd_matype=0)[1]
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        ATR_Threshold = self.feat.wma(ATR, timeperiod=20)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > WMA_Trend) & (Stoch_K > Stoch_D) & (Stoch_D < oversold_bound) & (ATR > ATR_Threshold)
        short_setup = (close < WMA_Trend) & (Stoch_K < Stoch_D) & (Stoch_D > overbought_bound) & (ATR > ATR_Threshold)

        # 6. Exit logic
        exit_long = (close < Rolling_Max - (exit_mult * ATR)) | (close < WMA_Trend)
        exit_short = (close > Rolling_Min + (exit_mult * ATR)) | (close > WMA_Trend)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
