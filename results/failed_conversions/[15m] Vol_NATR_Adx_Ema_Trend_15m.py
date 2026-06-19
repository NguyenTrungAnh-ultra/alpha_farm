from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 35)
        self.natr_threshold = float(self.natr_threshold if 'natr_threshold' in self.__dict__ else 5.0)
        ema_period = self.ema_period
        natr_threshold = self.natr_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema = self.feat.ema(close, timeperiod=20)
        natr = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > ema) & (feat.natr - self.op.shift(self.op, feat.natr, 1) >= 0.5 * natr) & (adx >= threshold)
        short_setup = (close < ema) & (self.op.shift(self.op, feat.natr, 1) <= feat.natrslope_threshold)
        exit_long = (close <= ema) | (feat.natr - self.op.shift(self.op, feat.natr, 2) < 0.5 * natr)
        exit_short = (close >= ema) & (self.op.shift(self.op, natr_slope), -1)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)