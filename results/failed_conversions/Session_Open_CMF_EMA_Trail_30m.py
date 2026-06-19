from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.EMA_Period = int(self.EMA_Period if 'EMA_Period' in self.__dict__ else 22)
        self.CMF_Threshold = float(self.CMF_Threshold if 'CMF_Threshold' in self.__dict__ else 0.0)
        EMA_Period = self.EMA_Period
        CMF_Threshold = self.CMF_Threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=20)
        cmf = self.feat.cmf(high, low, close, volume, timeperiod=14)
        long_setup = (close > open_price) & (cmf > 0.5)
        short_setup = (close < open_price) & (cmf < -0.5)
        exit_long = (ema >= close) | (cmf <= 0)
        exit_short = (ema <= close) | (cmf >= 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)