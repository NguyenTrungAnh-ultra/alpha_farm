from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.willr_period = int(getattr(self, 'willr_period', 9))
        self.vol_threshold = float(getattr(self, 'vol_threshold', 255.0))
        self.wma_period = int(getattr(self, 'wma_period', 14))
        self.exit_period = int(getattr(self, 'exit_period', 5))

        # 2. Local variables for parameters
        willr_period = self.willr_period
        vol_threshold = self.vol_threshold
        wma_period = self.wma_period
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        WillR = self.feat.willr(high, low, close, timeperiod=willr_period)
        Chaikin_Osc = self.feat.adosc(high, low, close, volume, fastperiod=3, slowperiod=10)
        WMA_Filter = self.feat.wma(close, timeperiod=wma_period)
        Micro_High = self.feat.max(high, timeperiod=exit_period)
        Micro_Low = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (WillR > -20.0) & (Chaikin_Osc > vol_threshold) & (close > WMA_Filter)
        short_setup = (WillR < -80.0) & (Chaikin_Osc < -vol_threshold) & (close < WMA_Filter)

        # 6. Exit logic
        exit_long = (WillR < -50.0) | (close < Micro_Low)
        exit_short = (WillR > -50.0) | (close > Micro_High)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
