from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.k_atr_mult = float(self.k_atr_mult if 'k_atr_mult' in self.__dict__ else 1.25)
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 22)
        k_atr_mult = self.k_atr_mult
        ema_period = self.ema_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_upper = self.feat.ema(close) + k * self.feat.atr(high, low, close)
        ema_lower = self.feat.ema(close) - k * self.feat.atr(high, low, close)
        long_setup = (close > ema_upper) & (self.feat.roc(close) > 0)
        short_setup = (close < ema_lower) & (self.feat.roc(close) < 0)
        exit_long = (close <= ema_lower) | ema_crosses_below_close
        exit_short = (close >= ema_upper) | ema_crosses_above_close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)