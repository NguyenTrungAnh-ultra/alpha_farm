from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.linreg_period = int(self.linreg_period if 'linreg_period' in self.__dict__ else 20)
        self.adx_threshold = float(self.adx_threshold if 'adx_threshold' in self.__dict__ else 25.0)
        linreg_period = self.linreg_period
        adx_threshold = self.adx_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        linreg_price = self.feat.linearreg(close, timeperiod=20)
        adx_regime = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (close > linreg_price) & (linreg_slope >= 0.5) & (adx_regime >= 20)
        short_setup = (close < linreg_price) & (linreg_slope <= -0.5) & (adx_regime >= 20)
        exit_long = (close < linreg_price) | (self.feat.atr(high, low, close, timeperiod=14) > self.feat.atr(high, low, close, timeperiod=3).mean())
        exit_short = (close > linreg_price) | (self.feat.atr(high, low, close, timeperiod=14) < 0.5)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)