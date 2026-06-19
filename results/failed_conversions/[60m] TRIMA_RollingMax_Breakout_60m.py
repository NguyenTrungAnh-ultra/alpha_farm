from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.timeperiod_trima = int(self.timeperiod_trima if 'timeperiod_trima' in self.__dict__ else 30)
        self.timeperiod_rolling_max = int(self.timeperiod_rolling_max if 'timeperiod_rolling_max' in self.__dict__ else 22)
        timeperiod_trima = self.timeperiod_trima
        timeperiod_rolling_max = self.timeperiod_rolling_max
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trend_line = self.feat.trima(close, timeperiod=21)
        resistance_level = self.op.rolling_max(high, timeperiod=20)
        volatility_measure = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (close >= resistance_level) & (trima_slope > 0)
        short_setup = (close <= Rolling_Max_Low_20) & (trima_slope < 0)
        exit_long = (close < TRIMA_Line) | atr_volatility_contraction
        exit_short = close > T3_Trend
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)