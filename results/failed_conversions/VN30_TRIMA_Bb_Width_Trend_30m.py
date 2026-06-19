from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.timeperiod_trima = int(self.timeperiod_trima if 'timeperiod_trima' in self.__dict__ else 22)
        self.atr_mult = float(self.atr_mult if 'atr_mult' in self.__dict__ else 1.25)
        timeperiod_trima = self.timeperiod_trima
        atr_mult = self.atr_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trima = self.feat.trima(close, timeperiod=20)
        bb_width = (bbands.upper - bbands.lower) / 1.5
        atr = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (close > trima) & (upper_band_width > atr * 0.8)
        short_setup = (close < trima) & (lower_band_width > atr * 0.8)
        exit_long = close <= trima
        exit_short = close >= trima
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)