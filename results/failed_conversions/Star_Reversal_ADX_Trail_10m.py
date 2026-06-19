from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 20)
        self.adx_period = int(self.adx_period if 'adx_period' in self.__dict__ else 15)
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 22)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.trailing_period = int(self.trailing_period if 'trailing_period' in self.__dict__ else 10)
        self.trailing_mult = float(self.trailing_mult if 'trailing_mult' in self.__dict__ else 2.75)
        ema_period = self.ema_period
        adx_period = self.adx_period
        adx_threshold = self.adx_threshold
        atr_period = self.atr_period
        trailing_period = self.trailing_period
        trailing_mult = self.trailing_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema = self.feat.ema(close, timeperiod=ema_period)
        adx = self.feat.adx(high, low, close, timeperiod=adx_period)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)
        morning_star = morningstar_pattern(open_price, high, low, close)
        evening_star = eveningstar_pattern(open_price, high, low, close)
        highest_high = self.feat.max(high, trailing_period)
        lowest_low = self.feat.min(low, trailing_period)
        long_setup = (morning_star == 100) & (close > ema) & (adx > adx_threshold)
        short_setup = (evening_star == -100) & (close < ema) & (adx > adx_threshold)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)