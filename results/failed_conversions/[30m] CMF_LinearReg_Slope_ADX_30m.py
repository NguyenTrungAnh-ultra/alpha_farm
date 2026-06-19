from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = float(self.adx_threshold if 'adx_threshold' in self.__dict__ else 35.0)
        self.cmf_ma_period = int(self.cmf_ma_period if 'cmf_ma_period' in self.__dict__ else 11)
        adx_threshold = self.adx_threshold
        cmf_ma_period = self.cmf_ma_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        cmf = self.feat.cmf(high, low, close)
        linearreg_slope_price = self.feat.linearreg_slope(close, timeperiod=20)
        adx_trend_strength = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (cmf > 0.5) & (linearreg_slope_price > self.feat.linearreg_slope(self.feat.ema(close), timeperiod=20)) & (adx_trend_strength > adx_threshold)
        short_setup = (cmf < -0.5) & (linearreg_slope_price < self.feat.linearreg_slope(self.feat.ema(close), timeperiod=20)) & (adx_trend_strength > adx_threshold)
        exit_long = close < midprice - self.feat.atr(high, low, close, timeperiod=14)
        exit_short = close > midprice + self.feat.atr(high, low, close, timeperiod=14)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)