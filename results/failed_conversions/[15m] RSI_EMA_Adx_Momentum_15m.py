from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 22)
        self.adx_threshold = float(self.adx_threshold if 'adx_threshold' in self.__dict__ else 17.5)
        ema_period = self.ema_period
        adx_threshold = self.adx_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=20)
        adx_trend = self.fead.adx(high, low, close, timeperiod=14)
        rsi_mom = self.feat.rsi(close, timeperiod=14)
        long_setup = (close > ema_fast) & (adx_trend >= 20.0)
        short_setup = (close < ema_fast) & (adx_trend >= 20.0)
        exit_long = close <= ema_fast
        exit_short = close >= ema_fast
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)