from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.5)
        self.sma_period = int(self.sma_period if 'sma_period' in self.__dict__ else 22)
        cmf_threshold = self.cmf_threshold
        sma_period = self.sma_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        cmf_flow = self.feat.cmf(high, low, close)
        macd_line = self.feat[0](close)
        sma_trend = self.feat.sma(close, timeperiod=20)
        long_setup = (cmf_flow > 0.5) & (macd_line > self.op.max(macd_line)) & (close >= sma_trend)
        short_setup = (cmf_flow < -0.5) & (macd_line < self.op.min(macd_line)) & (close <= sma_trend)
        exit_long = (close < sma_trend) | (macd_line < 0)
        exit_short = (close > sma_trend) | (macd_line > 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)