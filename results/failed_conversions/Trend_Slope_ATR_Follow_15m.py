from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.Slope_Period = int(self.Slope_Period if 'Slope_Period' in self.__dict__ else 24)
        self.EMA_Period = int(self.EMA_Period if 'EMA_Period' in self.__dict__ else 45)
        self.ATR_Multiplier = float(self.ATR_Multiplier if 'ATR_Multiplier' in self.__dict__ else 2.0)
        Slope_Period = self.Slope_Period
        EMA_Period = self.EMA_Period
        ATR_Multiplier = self.ATR_Multiplier
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        slope_20 = self.feat.linearreg_slope(close, timeperiod=20)
        ema_50 = self.feat.ema(close, timeperiod=50)
        atr_14 = self.feat.atr(high, low, close, timeperiod=14)
        long_setup = (slope > 2.0) & (close >= ema)
        short_setup = (slope < -2.0) & (close <= ema)
        exit_long = (close < ema) | (slope <= 0)
        exit_short = (close > ema) | (slope >= 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)