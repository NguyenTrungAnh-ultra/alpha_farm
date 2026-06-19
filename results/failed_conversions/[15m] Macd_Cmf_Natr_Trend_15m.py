from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.macd_threshold = float(self.macd_threshold if 'macd_threshold' in self.__dict__ else 2.5)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.65)
        macd_threshold = self.macd_threshold
        cmf_threshold = self.cmf_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        macd_hist = self.feat[0](close, timeperiod=14)
        cmf = self.feat.cmf(high, low, close, volume, timeperiod=20)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (macd_hist > 5.0) & (cmf > cmf_threshold)
        short_setup = (macd_hist < -5.0) & (cmf < -cmf_threshold)
        exit_long = (close < macd_line) | (macd_hist <= 0)
        exit_short = (close > macd_line) | (macd_hist >= 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)