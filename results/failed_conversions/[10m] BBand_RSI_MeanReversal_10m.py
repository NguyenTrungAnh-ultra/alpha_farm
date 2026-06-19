from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 30)
        self.rsi_entry_long = float(self.rsi_entry_long if 'rsi_entry_long' in self.__dict__ else 31.5)
        bb_period = self.bb_period
        rsi_entry_long = self.rsi_entry_long
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        bbands_lower = self.feat.bbands(high, low, close, timeperiod=20)[1]
        rsi_signal = self.feat.rsi(close, timeperiod=14)
        long_setup = (close <= bbands_lower) & (rsi_signal < 35)
        short_setup = (close >= self.op.max(BBands_upper)) & (rsi_signal > 60)
        exit_long = (close >= self.feat.bbands(high, low, close, timeperiod=20)[1]) | (rsi_signal > 75)
        exit_short = (close <= bbands_lower) & (rsi_signal < 35)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)