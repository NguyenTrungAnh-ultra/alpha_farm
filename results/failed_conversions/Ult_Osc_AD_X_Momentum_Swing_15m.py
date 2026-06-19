from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.AD_X_threshold = int(self.AD_X_threshold if 'AD_X_threshold' in self.__dict__ else 22)
        self.Ult_Osc_long_limit = float(self.Ult_Osc_long_limit if 'Ult_Osc_long_limit' in self.__dict__ else 50.0)
        AD_X_threshold = self.AD_X_threshold
        Ult_Osc_long_limit = self.Ult_Osc_long_limit
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ult_osc = self.feat.ultosc(close)
        adx = self.feat.adx(high, low, close, timeperiod=14)
        ema_trend = self.feat.ema(close, timeperiod=20)
        long_setup = (ult_osc > 50) & (adx > 20)
        short_setup = (ult_osc < 30) & (adx > 20)
        exit_long = close < ema_trend
        exit_short = close > ema_trend
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)