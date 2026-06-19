from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.fast_period = int(self.fast_period if 'fast_period' in self.__dict__ else 9)
        self.slow_period = int(self.slow_period if 'slow_period' in self.__dict__ else 20)
        self.adxr_period = int(self.adxr_period if 'adxr_period' in self.__dict__ else 14)
        self.adxr_threshold = int(self.adxr_threshold if 'adxr_threshold' in self.__dict__ else 22)
        self.vol_lookback = int(self.vol_lookback if 'vol_lookback' in self.__dict__ else 10)
        self.vol_mult = float(self.vol_mult if 'vol_mult' in self.__dict__ else 1.85)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 10)
        fast_period = self.fast_period
        slow_period = self.slow_period
        adxr_period = self.adxr_period
        adxr_threshold = self.adxr_threshold
        vol_lookback = self.vol_lookback
        vol_mult = self.vol_mult
        atr_period = self.atr_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=fast_period)
        apo = self.feat.apo(close, fastperiod=fast_period, slowperiod=slow_period, matype=0)
        apo_rising = self.feat.delta(apo) > 0
        adxr = self.feat.adxr(high, low, close, timeperiod=adxr_period)
        vol_sma = self.feat.sma(volume, timeperiod=vol_lookback)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)
        volume_burst = volume + 1e-08 > vol_sma * vol_mult
        long_setup = (apo > 0) & apo_rising & (adxr > adxr_threshold) & volume_burst
        short_setup = (apo < 0) & ~apo_rising & (adxr > adxr_threshold) & volume_burst
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)