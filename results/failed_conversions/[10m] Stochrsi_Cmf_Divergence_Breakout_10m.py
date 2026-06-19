from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.cmf_flow_threshold = float(self.cmf_flow_threshold if 'cmf_flow_threshold' in self.__dict__ else 0.0)
        self.natr_volatility_threshold = float(self.natr_volatility_threshold if 'natr_volatility_threshold' in self.__dict__ else 1.15)
        cmf_flow_threshold = self.cmf_flow_threshold
        natr_volatility_threshold = self.natr_volatility_threshold
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        stochrsi_fast = self.feat.stochrsi(close, timeperiod=10)[0]
        cmf_flow = self.feat.cmf(high, low, close)
        natr_volatility = self.feat.natr(high, low, close, timeperiod=20)
        long_setup = (close > close_shift(1)) & (stochrsi_fast < stochrsi_fast_shift(1)) & (cmf_flow >= cmf_flow_threshold)
        short_setup = (close < close_shift(1)) & (stochrsi_fast > stochrsi_fast_shift(1)) & (natr_volatility <= natr_volatility_threshold)
        exit_long = (stochrsi_fast > 80) & (close < close_shift(2))
        exit_short = (stochrsi_fast < 20) & (close > close_shift(2))
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)