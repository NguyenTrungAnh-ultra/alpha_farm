from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.roc_threshold = float(self.roc_threshold if 'roc_threshold' in self.__dict__ else 1.05)
        self.natr_filter_min = float(self.natr_filter_min if 'natr_filter_min' in self.__dict__ else 17.5)
        roc_threshold = self.roc_threshold
        natr_filter_min = self.natr_filter_min
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        EMA_fast = self.feat.ema(close, timeperiod=20)
        EMA_slow = self.feat.ema(close, timeperiod=50)
        ROC_Mom = self.feat.roc(close, timeperiod=14)
        NATR_Vol = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > EMA_slow) & (EMA_fast > EMA_slow) & (ROC_Mom >= 0.5)
        short_setup = (close < EMA_slow) & (EMA_fast < EMA_slow) & (ROC_Mom <= -0.5)
        exit_long = close < EMA_fast
        exit_short = close > EMA_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)