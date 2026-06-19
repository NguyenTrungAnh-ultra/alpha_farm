from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 17)
        self.vol_lookback = int(self.vol_lookback if 'vol_lookback' in self.__dict__ else 22)
        ema_period = self.ema_period
        vol_lookback = self.vol_lookback
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=param_1)
        natr_volatility = self.feat.natr(high, low, close, timeperiod=20)
        mean_natr_regime = self.op.rolling_mean(natr_volatility, timeperiod=param_2)
        long_setup = (close > ema_fast) & (natr_volatility > mean_natr_regime)
        short_setup = (close < ema_fast) & (mean_natr_regime >= natr_volatility)
        exit_long = (close <= ema_fast) | (natr_volatility < self.op.rolling_min(natr_volatility, timeperiod=10))
        exit_short = (close >= ema_fast) | (natr_volatility > mean_natr_regime)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)