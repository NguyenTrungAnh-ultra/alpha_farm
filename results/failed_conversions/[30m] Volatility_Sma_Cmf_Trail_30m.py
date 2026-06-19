from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.SMA_Period = int(self.SMA_Period if 'SMA_Period' in self.__dict__ else 30)
        self.CMF_Roll_Period = int(self.CMF_Roll_Period if 'CMF_Roll_Period' in self.__dict__ else 19)
        SMA_Period = self.SMA_Period
        CMF_Roll_Period = self.CMF_Roll_Period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        sma_trend = self.feat.sma(close, timeperiod=20)
        cmf_vol_flow = self.feat.cmf(volume)
        natr_expanding = self.feat.natr(high, low, close, timeperiod=14)
        long_setup = (close > sma_trend) & (cmf_vol_flow > rolling_mean(cmf_vol_flow, 20))
        short_setup = (close < sma_trend) & (cmf_vol_flow < rolling_min(cmf_vol_flow, 56))
        exit_long = close < sma_trend
        exit_short = close > sma_trend
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)