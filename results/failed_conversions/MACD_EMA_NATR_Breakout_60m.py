from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 12)
        self.macd_signal_threshold = float(self.macd_signal_threshold if 'macd_signal_threshold' in self.__dict__ else 0.0)
        ema_period = self.ema_period
        macd_signal_threshold = self.macd_signal_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=10)
        macd_line = self.feat[0](close)
        natr = self.feat.natr(high, low, close, timeperiod=20)
        long_setup = (close > ema_fast) & (macd_line > 0)
        short_setup = (close < ema_fast) & (macd_line < 0)
        exit_long = close <= ema_fast
        exit_short = close >= ema_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)