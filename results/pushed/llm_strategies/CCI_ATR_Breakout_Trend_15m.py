from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.sma_period = int(self.sma_period if 'sma_period' in self.__dict__ else 20)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.cci_period = int(self.cci_period if 'cci_period' in self.__dict__ else 20)
        self.multiplier = float(self.multiplier if 'multiplier' in self.__dict__ else 2.25)
        self.cci_threshold = int(self.cci_threshold if 'cci_threshold' in self.__dict__ else 115)
        sma_period = self.sma_period
        atr_period = self.atr_period
        cci_period = self.cci_period
        multiplier = self.multiplier
        cci_threshold = self.cci_threshold
        open_price = self.data.pv_open
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        sma = self.feat.sma(close, timeperiod=20)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        upper_band = sma + 2.0 * atr
        lower_band = sma - 2.0 * atr
        cci = self.feat.cci(high, low, close, timeperiod=20)
        long_setup = (close > upper_band) & (cci > 100) & (atr > 0.5)
        short_setup = (close < lower_band) & (cci < -100) & (atr > 0.5)
        exit_long = (close < sma) | (cci < 0)
        exit_short = (close > sma) | (cci > 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)