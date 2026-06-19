from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.wma_period = int(self.wma_period if 'wma_period' in self.__dict__ else 17)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.0)
        wma_period = self.wma_period
        cmf_threshold = self.cmf_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        wma_fast = self.feat.wma(close, timeperiod=10)
        cmf_flow = self.feat.cmf(high, low, close)
        roc_mom = self.feat.roc(close, timeperiod=14)
        long_setup = (close > wma_fast) & (cmf_flow > -0.5)
        short_setup = (close < wma_fast) & (cmf_flow < 0.5)
        exit_long = close < self.feat.sma(close, timeperiod=20)
        exit_short = close > self.feat.sma(close, timeperiod=20)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)