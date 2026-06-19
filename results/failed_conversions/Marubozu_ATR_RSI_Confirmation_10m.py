from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.EMA_period = int(self.EMA_period if 'EMA_period' in self.__dict__ else 25)
        self.ATR_period = int(self.ATR_period if 'ATR_period' in self.__dict__ else 20)
        self.atr_multiplier = float(self.atr_multiplier if 'atr_multiplier' in self.__dict__ else 2.0)
        self.rsi_exit_upper = int(self.rsi_exit_upper if 'rsi_exit_upper' in self.__dict__ else 77)
        self.rsi_exit_lower = int(self.rsi_exit_lower if 'rsi_exit_lower' in self.__dict__ else 22)
        EMA_period = self.EMA_period
        ATR_period = self.ATR_period
        atr_multiplier = self.atr_multiplier
        rsi_exit_upper = self.rsi_exit_upper
        rsi_exit_lower = self.rsi_exit_lower
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        marubozu = self.feat.marubozu_pattern(open_price, high, low, close)
        ema_fast = self.feat.ema(close, timeperiod=EMA_period)
        rsi = self.feat.rsi(close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=ATR_period)
        long_setup = (marubozu == 100) & (rsi > 50) & (close > ema_fast)
        short_setup = (marubozu == -100) & (rsi < 50) & (close < ema_fast)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)