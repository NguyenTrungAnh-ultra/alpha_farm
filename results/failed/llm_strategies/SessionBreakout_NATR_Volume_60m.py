from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.session_window = int(self.session_window if 'session_window' in self.__dict__ else 6)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.volume_sma_period = int(self.volume_sma_period if 'volume_sma_period' in self.__dict__ else 12)
        self.natr_threshold = float(self.natr_threshold if 'natr_threshold' in self.__dict__ else 0.65)
        self.exit_ema_period = int(self.exit_ema_period if 'exit_ema_period' in self.__dict__ else 6)
        session_window = self.session_window
        atr_period = self.atr_period
        volume_sma_period = self.volume_sma_period
        natr_threshold = self.natr_threshold
        exit_ema_period = self.exit_ema_period
        open_price = self.data.pv_open
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        natr = self.feat.natr(high, low, close, timeperiod=atr_period)
        rolling_high = self.feat.rolling_max(high, window=session_window)
        rolling_low = self.feat.rolling_min(low, window=session_window)
        prev_high = self.op.shift(rolling_high)
        prev_low = self.op.shift(rolling_low)
        volume_sma = self.feat.sma(volume, timeperiod=volume_sma_period)
        ema_exit = self.feat.ema(close, timeperiod=exit_ema_period)
        long_setup = (close > prev_high) & (natr > natr_threshold) & (volume > volume_sma)
        short_setup = (close < prev_low) & (natr > natr_threshold) & (volume > volume_sma)
        exit_long = close < ema_exit
        exit_short = close > ema_exit
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)