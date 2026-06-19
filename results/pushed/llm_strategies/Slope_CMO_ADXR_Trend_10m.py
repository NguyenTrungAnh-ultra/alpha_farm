from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.cmo_period = 200
        self.adxr_period = 100
        self.slope_period = 30
        self.cmo_threshold = 20
        self.adxr_threshold = 10
        cmo_period = self.cmo_period
        adxr_period = self.adxr_period
        slope_period = self.slope_period
        cmo_threshold = self.cmo_threshold
        adxr_threshold = self.adxr_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        lin_slope = self.feat.linearreg_slope(close, timeperiod=20)
        cmo = self.feat.cmo(close, timeperiod=14)
        adxr = self.feat.adxr(high, low, close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        rolling_max_close = self.feat.max(close, timeperiod=10)
        long_setup = (lin_slope > 0) & (cmo > cmo_threshold) & (adxr > adxr_threshold)
        short_setup = (lin_slope < 0) & (cmo < -cmo_threshold) & (adxr > adxr_threshold)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
