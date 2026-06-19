from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 85)
        self.slope_period = int(self.slope_period if 'slope_period' in self.__dict__ else 35)
        self.atr_mult = float(self.atr_mult if 'atr_mult' in self.__dict__ else 2.0)
        ema_period = self.ema_period
        slope_period = self.slope_period
        atr_mult = self.atr_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope_trend = self.feat.linearreg_slope(close, timeperiod=20)
        price_ma = self.feat.ema(close, timeperiod=50)
        volatility_atr = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (slope_trend > 0) & (close >= price_ma)
        short_setup = (slope_trend < 0) & (close <= price_ma)
        exit_long = close < price_ma - self.params.atr_mult * volatility_atr
        exit_short = close > price_ma + self.params.atr_mult * volatility_atr
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)