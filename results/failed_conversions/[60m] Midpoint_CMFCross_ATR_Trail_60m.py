from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.CMF_threshold_low = float(self.CMF_threshold_low if 'CMF_threshold_low' in self.__dict__ else -0.1)
        self.CMF_threshold_high = float(self.CMF_threshold_high if 'CMF_threshold_high' in self.__dict__ else 0.6)
        self.ATR_mult_low = float(self.ATR_mult_low if 'ATR_mult_low' in self.__dict__ else 1.75)
        CMF_threshold_low = self.CMF_threshold_low
        CMF_threshold_high = self.CMF_threshold_high
        ATR_mult_low = self.ATR_mult_low
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        midpoint_channel = self.feat.midprice(high, low)
        cmf_flow = self.feat.cmf(close, volume, timeperiod=10)
        atr_volatility = self.feat.atr(high, low, close, timeperiod=20)
        long_setup = (close > midpoint_channel) & (cmf_flow > 0.5)
        short_setup = (close < midpoint_channel) & (cmf_flow < -0.5)
        exit_long = close < midpoint_channel - atr_volatility * 1.2
        exit_short = close > midpoint_channel + atr_volatility * 1.2
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)