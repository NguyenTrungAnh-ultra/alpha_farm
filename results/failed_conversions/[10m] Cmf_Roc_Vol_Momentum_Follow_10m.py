from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.param_cmft = float(self.param_cmft if 'param_cmft' in self.__dict__ else 0.5)
        self.param_roct = int(self.param_roct if 'param_roct' in self.__dict__ else 12)
        param_cmft = self.param_cmft
        param_roct = self.param_roct
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        cmf = self.feat.cmf(volume, close, timeperiod=20)
        roc = self.feat.roc(close, timeperiod=14)
        long_setup = (cmf > param_cmft) & (roc > param_roct)
        short_setup = (cmf < -param_cmft) & (roc < -param_roct)
        exit_long = (cmf < 0.5 * param_exit_thresh) | (roc <= 0)
        exit_short = (cmf > 0.5 * param_exit_thresh_neg) | (roc >= 0)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)