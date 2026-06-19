from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = int(self.adx_threshold if 'adx_threshold' in self.__dict__ else 27)
        self.rsi_period = int(self.rsi_period if 'rsi_period' in self.__dict__ else 17)
        adx_threshold = self.adx_threshold
        rsi_period = self.rsi_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        rsi_fast = self.feat.rsi(close, timeperiod=14)
        ema_trend = self.feat.ema(close, timeperiod=20)
        adx_regime = self.feat.adx(high, low, close, timeperiod=14)
        long_setup = (close >= self.op.shift(self.op, close)) & (rsi_fast <= self.op.shift(self.op, rsi_fast)) & (adx_regime > 20)
        short_setup = (close < self.op.shift(self.op, close)) & (rsi_fast >= self.op.shift(self.op, rsi_fast)) & (adx_regime > 20)
        exit_long = (close < ema_trend) | (rsi_fast <= self.op.shift(self.op, rsi_fast))
        exit_short = (close > ema_trend) | (rsi_fast >= self.op.shift(self.op, rsi_fast))
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)