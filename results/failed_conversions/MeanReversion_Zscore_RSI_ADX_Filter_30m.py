from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.zscore_threshold_low = float(self.zscore_threshold_low if 'zscore_threshold_low' in self.__dict__ else -2.75)
        self.rsi_oversold_level = int(self.rsi_oversold_level if 'rsi_oversold_level' in self.__dict__ else 34)
        zscore_threshold_low = self.zscore_threshold_low
        rsi_oversold_level = self.rsi_oversold_level
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        rolling_zscore = self.feat.rolling_zscore(close, timeperiod=20)
        rsi_14 = self.feat.rsi(high, low, close, timeperiod=14)
        adx_14 = self.feat.adx(high, low, close, timeperiod=14)
        rolling_adr_mean = self.feat.ema(self.feat.atr(high, low, close, timeperiod=14), timeperiod=20)
        long_setup = (self.op.abs(adx_14) < 35) & (rolling_zscore < -2.0) & (rsi_14 <= 30)
        short_setup = (self.op.abs(adx_14) < 35) & (rolling_zscore > 2.0) & (rsi_14 >= 70)
        exit_long = (rolling_zscore >= -1.0) | closing_price_crosses_mean
        exit_short = (rolling_zscore <= 1.0) | closing_price_crosses_mean
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)