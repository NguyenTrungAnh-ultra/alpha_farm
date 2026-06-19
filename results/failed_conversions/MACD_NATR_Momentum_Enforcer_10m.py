from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 32)
        self.macd_threshold = float(self.macd_threshold if 'macd_threshold' in self.__dict__ else 0.0)
        ema_period = self.ema_period
        macd_threshold = self.macd_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        macd_hist = self.feat[0](close)
        ema_trend = self.feat.ema(close, timeperiod=param_ema_period)
        natr_vol = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (macd_hist > 0) & (close >= ema_trend)
        short_setup = (macd_hist < 0) & (close <= ema_trend)
        exit_long = (macd_hist < 0) | (close < ema_trend)
        exit_short = (macd_hist > 0) | (close > ema_trend)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)