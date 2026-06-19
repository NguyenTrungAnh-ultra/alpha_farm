from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.nATR_period = int(self.nATR_period if 'nATR_period' in self.__dict__ else 25)
        nATR_period = self.nATR_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ppo_val = self.feat.ppo(close, timeperiod=14)
        natr_vol = self.feat.natr(high, low, close, timeperiod=param_nATR_period)
        long_setup = self.op.crossed_above(ppo_val, self.op.shift(self.op, ppo_val)) & (natr_vol > self.op.shift(natr_vol, 1))
        short_setup = self.op.crossed_below(ppo_val, self.op.shift(self.op, ppo_val)) & (natr_vol < self.op.shift(natr_vol, 1))
        exit_long = self.op.crossed_below(ppo_val, self.op.shift(self.op, ppo_val))
        exit_short = self.op.crossed_above(ppo_val, self.op.shift(self.op, ppo_val))
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)