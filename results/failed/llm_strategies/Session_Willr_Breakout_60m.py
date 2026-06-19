from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.N = int(self.N if 'N' in self.__dict__ else 5)
        self.atr_threshold = float(self.atr_threshold if 'atr_threshold' in self.__dict__ else 1.75)
        N = self.N
        atr_threshold = self.atr_threshold
        open_price = self.data.pv_open
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        session_high = self.op.shift(self.feat.rolling_max(high, timeperiod=N))
        session_low = self.op.shift(self.feat.rolling_min(low, timeperiod=N))
        session_mid = (session_high + session_low) / 2
        willr = self.feat.willr(high, low, close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (close > session_high) & (willr > -20) & (atr > atr_threshold)
        short_setup = (close < session_low) & (willr < -80) & (atr > atr_threshold)
        exit_long = close < session_mid
        exit_short = close > session_mid
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)