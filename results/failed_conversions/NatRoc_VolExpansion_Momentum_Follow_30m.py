from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 24)
        self.natr_period = int(self.natr_period if 'natr_period' in self.__dict__ else 17)
        ema_period = self.ema_period
        natr_period = self.natr_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        natr = self.feat.natr(high, low, close, timeperiod=20)
        ema = self.feat.ema(close, timeperiod=14)
        roc = self.op.pct_change(self.feat.close)
        long_setup = (natr > rolling_mean(natr)) & (close >= ema)
        short_setup = (rolling_mean(natr) - natr > 0.1 * natr) & (close <= ema)
        exit_long = (close < ema) | (roc <= 0)
        exit_short = (close > ema) | (roc >= 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)