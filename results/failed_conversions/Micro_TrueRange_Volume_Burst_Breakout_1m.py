from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.param_a = float(self.param_a if 'param_a' in self.__dict__ else 1.25)
        self.param_b = float(self.param_b if 'param_b' in self.__dict__ else 2.0)
        self.param_c = float(self.param_c if 'param_c' in self.__dict__ else 2.0)
        param_a = self.param_a
        param_b = self.param_b
        param_c = self.param_c
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        atr_fast = self.feat.atr(high, low, close, timeperiod=5)
        atr_slow = self.feat.atr(high, low, close, timeperiod=10)
        volume_wma = self.feat.wma(volume, timeperiod=10)
        rolling_high_5 = self.feat.max(high, timeperiod=5)
        rolling_low_5 = self.feat.min(low, timeperiod=5)
        shift_close = self.op.shift(self.feat, close)
        long_setup = (close > shift_close + param_a * atr_fast) & (volume > param_b * volume_wma)
        short_setup = (close < shift_close - param_a * atr_fast) & (volume > param_b * volume_wma)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)