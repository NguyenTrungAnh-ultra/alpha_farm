from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.sar_acc = 0.02
        self.sar_max = 0.09
        self.mfi_period = 20
        self.mfi_offset = 5.95
        self.exit_period = 50
        self.exit_mult = 1.75
        sar_acc = self.sar_acc
        sar_max = self.sar_max
        mfi_period = self.mfi_period
        mfi_offset = self.mfi_offset
        exit_period = self.exit_period
        exit_mult = self.exit_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        sar = self.feat.sar(high, low, acceleration=sar_acc, maximum=sar_max)
        mfi = self.feat.mfi(high, low, close, volume, timeperiod=mfi_period)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        rolling_max = self.feat.max(high, timeperiod=exit_period)
        rolling_min = self.feat.min(low, timeperiod=exit_period)
        long_setup = (close > sar) & (mfi > 50.0 + mfi_offset)
        short_setup = (close < sar) & (mfi < 50.0 - mfi_offset)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
