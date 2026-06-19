from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ppo_fast = int(self.ppo_fast if 'ppo_fast' in self.__dict__ else 10)
        self.ppo_slow = int(self.ppo_slow if 'ppo_slow' in self.__dict__ else 30)
        self.ppo_signal = int(self.ppo_signal if 'ppo_signal' in self.__dict__ else 10)
        self.linreg_period = int(self.linreg_period if 'linreg_period' in self.__dict__ else 20)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.atr_threshold = float(self.atr_threshold if 'atr_threshold' in self.__dict__ else 9.0)
        ppo_fast = self.ppo_fast
        ppo_slow = self.ppo_slow
        ppo_signal = self.ppo_signal
        linreg_period = self.linreg_period
        atr_period = self.atr_period
        atr_threshold = self.atr_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ppo = self.feat.ppo(close, fastperiod=ppo_fast, slowperiod=ppo_slow, signalperiod=ppo_signal)
        linregslope = self.feat.linearreg_slope(close, timeperiod=linreg_period)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)
        long_setup = (ppo > 0) & (linregslope > 0) & (atr > atr_threshold)
        short_setup = (ppo < 0) & (linregslope < 0) & (atr > atr_threshold)
        exit_long = self.op.crossed_below(ppo, 0)
        exit_short = self.op.crossed_above(ppo, 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)