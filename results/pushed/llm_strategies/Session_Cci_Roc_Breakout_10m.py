from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.SMA_Period = 20
        self.CCI_Threshold = 172.5
        SMA_Period = self.SMA_Period
        CCI_Threshold = self.CCI_Threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        sma_trend = self.feat.sma(close, timeperiod=30)
        cci_mom = self.feat.cci(high, low, close)
        roc_accel = self.feat.roc(close, timeperiod=14)
        long_setup = (close > sma_trend) & (cci_mom > 50)
        short_setup = (close < sma_trend) & (cci_mom < -50)
        exit_long = (close < sma_trend) | (cci_mom < 20)
        exit_short = (close > sma_trend) | (cci_mom > -20)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
