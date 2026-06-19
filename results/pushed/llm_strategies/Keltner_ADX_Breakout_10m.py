from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 22)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.multiplier = float(self.multiplier if 'multiplier' in self.__dict__ else 2.25)
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 30)
        ema_period = self.ema_period
        atr_period = self.atr_period
        multiplier = self.multiplier
        adx_threshold = self.adx_threshold
        open_price = self.data.pv_open
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_mid = self.feat.ema(close, timeperiod=ema_period)
        atr_val = self.feat.atr(high, low, close, timeperiod=atr_period)
        upper = ema_mid + multiplier * atr_val
        lower = ema_mid - multiplier * atr_val
        adx = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (close > upper) & (adx > adx_threshold)
        short_setup = (close < lower) & (adx > adx_threshold)
        exit_long = close < ema_mid
        exit_short = close > ema_mid
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)