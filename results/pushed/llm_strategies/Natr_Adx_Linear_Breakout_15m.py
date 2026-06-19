from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.LinearPeriod = 50
        self.NATR_Period = 60
        self.ADX_Threshold = 24.75
        LinearPeriod = self.LinearPeriod
        NATR_Period = self.NATR_Period
        ADX_Threshold = self.ADX_Threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        linearreg_pivot = self.feat.linearreg(close, timeperiod=20)
        natr_filter = self.feat.natr(high, low, close, timeperiod=14)
        adx_regime = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (close >= linearreg_pivot + natr_filter * 0.5) & (adx_regime > 20)
        short_setup = (close <= linearreg_pivot - natr_filter * 0.5) & (adx_regime > 20)
        exit_long = close < linearreg_pivot - natr_filter * 1.5
        exit_short = close > linearreg_pivot + natr_filter * 1.5
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
