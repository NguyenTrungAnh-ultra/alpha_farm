from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.trix_period = int(self.trix_period if 'trix_period' in self.__dict__ else 22)
        self.adx_period = int(self.adx_period if 'adx_period' in self.__dict__ else 16)
        self.adx_entry_threshold = float(self.adx_entry_threshold if 'adx_entry_threshold' in self.__dict__ else 25.0)
        self.adx_exit_threshold = float(self.adx_exit_threshold if 'adx_exit_threshold' in self.__dict__ else 20.0)
        self.exit_lookback = int(self.exit_lookback if 'exit_lookback' in self.__dict__ else 10)
        self.atr_mult = float(self.atr_mult if 'atr_mult' in self.__dict__ else 2.25)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        trix_period = self.trix_period
        adx_period = self.adx_period
        adx_entry_threshold = self.adx_entry_threshold
        adx_exit_threshold = self.adx_exit_threshold
        exit_lookback = self.exit_lookback
        atr_mult = self.atr_mult
        atr_period = self.atr_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trix = self.feat.trix(close, timeperiod=trix_period)
        adx = self.feat.adx(high, low, close, timeperiod=adx_period)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)
        trix_prev = self.op.shift(self.op, trix)
        highest_high = self.feat.max(high, exit_lookback)
        lowest_low = self.feat.min(low, exit_lookback)
        long_setup = (trix > 0) & (trix_prev <= 0) & (adx > adx_entry_threshold)
        short_setup = (trix < 0) & (trix_prev >= 0) & (adx > adx_entry_threshold)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)