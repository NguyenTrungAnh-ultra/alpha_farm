from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period_fast = 200
        self.slope_threshold = 1.0
        ema_period_fast = self.ema_period_fast
        slope_threshold = self.slope_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        t3_trend = self.feat.tema(close, timeperiod=20)
        linear_reg_slope = self.feat.linearreg_slope(open_price, close, timeperiod=14)
        atr_filter = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (close > t3_trend) & (linear_reg_slope > 0.5) & (atr_filter > 2.0)
        short_setup = (close < t3_trend) & (linear_reg_slope < -0.5) & (atr_filter > 2.0)
        exit_long = (close <= t3_trend) | (t3_trend + atr_filter * 1.5 >= close)
        exit_short = (close >= t3_trend) | (t3_trend - atr_filter * 1.5 <= close)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
