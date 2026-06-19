from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 17)
        self.vwap_period = int(self.vwap_period if 'vwap_period' in self.__dict__ else 40)
        self.natr_threshold = float(self.natr_threshold if 'natr_threshold' in self.__dict__ else 1.9)
        ema_period = self.ema_period
        vwap_period = self.vwap_period
        natr_threshold = self.natr_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        rollingvwap = self.feat.rolling_vwap(close, timeperiod=20)
        ema_fast = self.feat.ema(close, timeperiod=14)
        natr = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > rollingvwap) & (ema_fast < self.op.shift(self.op, rolling_vwap, 1)) & (natr > param_natr_threshold)
        short_setup = (close < rollingvwap) & (ema_fast > self.op.shift(self.op, rolling_vwap, 1)) & (natr > param_natr_threshold)
        exit_long = close <= rolling_vwap
        exit_short = close >= rolling_vwap
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)