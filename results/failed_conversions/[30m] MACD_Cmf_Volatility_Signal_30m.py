from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.macd_fast_period = int(self.macd_fast_period if 'macd_fast_period' in self.__dict__ else 11)
        self.cmf_rolling_mean_period = int(self.cmf_rolling_mean_period if 'cmf_rolling_mean_period' in self.__dict__ else 12)
        macd_fast_period = self.macd_fast_period
        cmf_rolling_mean_period = self.cmf_rolling_mean_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        macd_hist = self.feat[0](close, timeperiod=12).histogram
        cmf_signal = self.feat.cmf(high, low, close, volume)
        natr_filt = self.feat.natr(high, low, close)
        long_setup = (macd_hist > 0.5) & CMF_Signal_crosses_above_rolling_mean(cmf_signal, period=14)
        short_setup = (macd_hist < -0.5) & CMF_Signal_crosses_below_rolling_mean(cmf_signal, period=14)
        exit_long = macd_hist < 0
        exit_short = macd_hist > 0
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)