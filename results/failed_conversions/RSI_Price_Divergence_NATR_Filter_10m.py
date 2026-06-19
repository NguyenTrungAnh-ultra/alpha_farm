from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 27)
        self.rsi_threshold_diff = float(self.rsi_threshold_diff if 'rsi_threshold_diff' in self.__dict__ else 0.05)
        ema_period = self.ema_period
        rsi_threshold_diff = self.rsi_threshold_diff
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_20 = self.feat.ema(close, timeperiod=20)
        rsi_14 = self.feat.rsi(high, low, close, timeperiod=14)
        natr_14 = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close < ema_20) & (rsi_14 > rsi_14[self.op.shift(self.op, 5)])
        short_setup = (close > ema_20) & (rsi_14 < rsi_14[self.op.shift(self.op, 5)])
        exit_long = close >= ema_20
        exit_short = close <= ema_20
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)