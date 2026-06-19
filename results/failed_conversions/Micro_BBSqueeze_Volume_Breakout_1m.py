from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 20)
        self.squeeze_threshold = float(self.squeeze_threshold if 'squeeze_threshold' in self.__dict__ else 0.085)
        self.vol_multiplier = float(self.vol_multiplier if 'vol_multiplier' in self.__dict__ else 2.0)
        bb_period = self.bb_period
        squeeze_threshold = self.squeeze_threshold
        vol_multiplier = self.vol_multiplier
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        bb_upper = self.feat.bbands(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0).upper
        bb_middle = self.feat.bbands(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0).middle
        bb_lower = self.feat.bbands(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0).lower
        bandwidth = (bb_upper - bb_lower) / (bb_middle + 1e-08)
        volume_sma = self.feat.sma(volume, timeperiod=10)
        long_setup = (bandwidth < squeeze_threshold) & (close > bb_upper) & (volume > volume_sma * vol_multiplier)
        short_setup = (bandwidth < squeeze_threshold) & (close < bb_lower) & (volume > volume_sma * vol_multiplier)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)