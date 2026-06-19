from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 18)
        self.rsi_period = int(self.rsi_period if 'rsi_period' in self.__dict__ else 13)
        ema_period = self.ema_period
        rsi_period = self.rsi_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_trend = self.feat.ema(close, timeperiod=ema_period)
        rsi_oscillator = self.feat.rsi(high, low, close, timeperiod=rsi_period)
        macd_hist = self.feat[0](close)
        long_setup = (close > ema_trend) & (rsi_oscillator < 35.0)
        short_setup = (close < ema_trend) & (rsi_oscillator > 65.0)
        exit_long = (close < ema_trend) | (rsi_oscillator >= 45.0)
        exit_short = (close > ema_trend) | (rsi_oscillator <= 35.0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)