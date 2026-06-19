from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period_fast = int(self.ema_period_fast if 'ema_period_fast' in self.__dict__ else 10)
        self.linearreg_period = int(self.linearreg_period if 'linearreg_period' in self.__dict__ else 22)
        self.cmf_period = int(self.cmf_period if 'cmf_period' in self.__dict__ else 40)
        self.stochrsi_fast_k = float(self.stochrsi_fast_k if 'stochrsi_fast_k' in self.__dict__ else 2.0)
        ema_period_fast = self.ema_period_fast
        linearreg_period = self.linearreg_period
        cmf_period = self.cmf_period
        stochrsi_fast_k = self.stochrsi_fast_k
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=10)
        linearreg_slope = self.feat.linearreg_slope(close, timeperiod=20)
        cmf = self.feat.cmf(high, low, close, volume, timeperiod=50)
        stochrsi_fast = self.feat.stochrsi(close, timeperiod=14)[0]
        long_setup = (linearreg_slope > 0.2) & (cmf > EMA_fast_of_CMF) & (stochrsi_fast < 35)
        short_setup = (linearreg_slope < -0.2) & (cmf < EMA_fast_of_CMF) & (stochrsi_fast > 65)
        exit_long = (linearreg_slope <= 0) | (stochrsi_fast >= 80)
        exit_short = (linearreg_slope >= 0) | (stochrsi_fast <= 20)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)