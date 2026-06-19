from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.aroon_period = int(self.aroon_period if 'aroon_period' in self.__dict__ else 20)
        self.adx_period = int(self.adx_period if 'adx_period' in self.__dict__ else 22)
        self.cmo_period = int(self.cmo_period if 'cmo_period' in self.__dict__ else 20)
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 30)
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 30)
        self.cmo_threshold = int(self.cmo_threshold if 'cmo_threshold' in self.__dict__ else 15)
        aroon_period = self.aroon_period
        adx_period = self.adx_period
        cmo_period = self.cmo_period
        ema_period = self.ema_period
        adx_threshold = self.adx_threshold
        cmo_threshold = self.cmo_threshold
        open_price = self.data.pv_open
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        aroon_osc = self.feat.aroonosc(high, low, timeperiod=14)
        adx = self.feat.adx(high, low, close, timeperiod=14)
        cmo = self.feat.cmo(close, timeperiod=14)
        ema = self.feat.ema(close, timeperiod=20)
        long_setup = (aroon_osc > 0) & (adx > 25) & (cmo > 20) & (close > ema)
        short_setup = (aroon_osc < 0) & (adx > 25) & (cmo < -20) & (close < ema)
        exit_long = (aroon_osc < 0) | (cmo < 0) | (close < ema)
        exit_short = (aroon_osc > 0) | (cmo > 0) | (close > ema)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)