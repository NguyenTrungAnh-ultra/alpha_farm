from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period_1 = int(self.ema_period_1 if 'ema_period_1' in self.__dict__ else 20)
        self.ema_period_2 = int(self.ema_period_2 if 'ema_period_2' in self.__dict__ else 22)
        ema_period_1 = self.ema_period_1
        ema_period_2 = self.ema_period_2
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        tema_fast = self.feat.ema(close, timeperiod=20)
        cmf_flow = self.feat.cmf(open_price)
        engulfing_signal = self.feat.engulfing_pattern(high, low)
        long_setup = (cmf > 0.1) & (close > tema_fast)
        short_setup = (cmf < -0.1) & (close < tema_fast)
        exit_long = close < self.feat.ema(25)
        exit_short = close > self.feat.ema(25)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)