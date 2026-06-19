from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.period = int(self.period if 'period' in self.__dict__ else 35)
        self.entry_threshold = float(self.entry_threshold if 'entry_threshold' in self.__dict__ else 2.25)
        self.exit_threshold = float(self.exit_threshold if 'exit_threshold' in self.__dict__ else 0.65)
        self.adx_threshold = float(self.adx_threshold if 'adx_threshold' in self.__dict__ else 20.0)
        period = self.period
        entry_threshold = self.entry_threshold
        exit_threshold = self.exit_threshold
        adx_threshold = self.adx_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        volume_safe = volume + 1e-08
        vwap = self.op.rolling_sum(close * volume, period) / self.op.rolling_sum(volume_safe, period)
        std_price = self.op.rolling_std(close, period)
        zscore = (close - vwap) / std_price
        adx = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (zscore < -entry_threshold) & (adx < adx_threshold)
        short_setup = (zscore > entry_threshold) & (adx < adx_threshold)
        exit_long = zscore > -exit_threshold
        exit_short = zscore < exit_threshold
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)