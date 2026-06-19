from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.timeperiod_roc = int(self.timeperiod_roc if 'timeperiod_roc' in self.__dict__ else 6)
        self.threshold_stoch_low = float(self.threshold_stoch_low if 'threshold_stoch_low' in self.__dict__ else 17.5)
        self.threshold_stoch_high = float(self.threshold_stoch_high if 'threshold_stoch_high' in self.__dict__ else 82.5)
        timeperiod_roc = self.timeperiod_roc
        threshold_stoch_low = self.threshold_stoch_low
        threshold_stoch_high = self.threshold_stoch_high
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        stochrs = self.feat.stochrsi(close, timeperiod=14)[0]
        roc = self.feat.roc(close, timeperiod=5)
        long_setup = (close >= close_shift(1)) & (stochrs < 30) & (roc > roc_shift(1))
        short_setup = (close <= close_shift(1)) & (stochrs > 70) & (roc < roc_shift(1))
        exit_long = (close <= close_shift(1)) & (stochrs >= 50)
        exit_short = (close >= close_shift(1)) & (stochrs <= 30)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)