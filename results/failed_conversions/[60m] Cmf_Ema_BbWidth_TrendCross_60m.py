from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 30)
        self.cmf_threshold = float(self.cmf_threshold if 'cmf_threshold' in self.__dict__ else 0.05)
        ema_period = self.ema_period
        cmf_threshold = self.cmf_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=20)
        cmf_flow = self.feat.cmf(open_price, volume, timeperiod=14)
        bb_upper = self.feat.bbands(high, low, close, timeperiod=20).upper
        bb_lower = self.feat.bbands(high, low, close, timeperiod=20).lower
        long_setup = (close > ema_fast) & (cmf_flow >= 0.15) & (self.op.shift(self.op, cmf_flow, -1), cmf_flow)
        short_setup = (close < ema_fast) & (cmf_flow <= -0.15)
        exit_long = (close < ema_fast) | (cmf_flow < 0)
        exit_short = (close > ema_fast) | (cmf_flow > 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)