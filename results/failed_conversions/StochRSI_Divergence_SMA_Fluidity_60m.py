from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.sma_period = int(self.sma_period if 'sma_period' in self.__dict__ else 40)
        self.stochrsi_threshold_low = float(self.stochrsi_threshold_low if 'stochrsi_threshold_low' in self.__dict__ else 25.0)
        self.atr_multiplier = float(self.atr_multiplier if 'atr_multiplier' in self.__dict__ else 1.4)
        sma_period = self.sma_period
        stochrsi_threshold_low = self.stochrsi_threshold_low
        atr_multiplier = self.atr_multiplier
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        stochrsi = self.feat.stochrsi(close, timeperiod=14)[0]
        atr = self.feat.atr(high, low, close, timeperiod=10)
        long_setup = (close < close_shift(1)) & (stochrsi > 30)
        short_setup = (close > close_shift(1)) & (stochrsi < 70) & ~(close >= low_shift(-1))
        exit_long = ((close >= high_shift(-1)) | self.op.crossed_below_value(stochrsi, value=50),)
        exit_short = (close <= high_shift(-1)) | self.op.crossed_above_value(stochrsi, value=50)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)