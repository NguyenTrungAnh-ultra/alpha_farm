from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 30)
        self.natr_roll_factor = float(self.natr_roll_factor if 'natr_roll_factor' in self.__dict__ else 5.5)
        ema_period = self.ema_period
        natr_roll_factor = self.natr_roll_factor
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_trend = self.feat.ema(close, timeperiod=20)
        natr_volatility = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > ema_trend) & (self.feat.roc(close) > 0.5) & (natr_volatility > self.op.shift(self.op, self.feat.atr(natr_volatility), 3))
        short_setup = (close < ema_trend) & (-self.feat.roc(close) > -1.0) & (natr_volatility > self.op.shift(self.op, self.feat.atr(natr_volatility), 3))
        exit_long = close < ema_trend
        exit_short = close > ema_trend
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)