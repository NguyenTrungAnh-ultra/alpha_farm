from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 17)
        self.rsi_threshold = float(self.rsi_threshold if 'rsi_threshold' in self.__dict__ else 55.0)
        ema_period = self.ema_period
        rsi_threshold = self.rsi_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_20 = self.feat.ema(close, timeperiod=ema_period)
        rsi_14 = self.feat.rsi(high, low, close, timeperiod=rsi_level)
        atr_14 = self.feat.atr(high, low, close, timeperiod=atr_period)
        long_setup = (close < ema_20) & (rsi_14 <= rsi_threshold)
        short_setup = (close > ema_20) & (rsi_14 >= 65)
        exit_long = (atr_14 < atr_target) & (close >= ema_20)
        exit_short = (atr_14 < atr_target) & (close <= ema_20)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)