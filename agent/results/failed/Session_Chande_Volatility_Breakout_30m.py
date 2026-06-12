from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.range_period = int(getattr(self, 'range_period', 30))
        self.cmo_period = int(getattr(self, 'cmo_period', 21))
        self.cmo_threshold = float(getattr(self, 'cmo_threshold', 22.5))
        self.exit_period = int(getattr(self, 'exit_period', 25))

        # 2. Local variables for parameters
        range_period = self.range_period
        cmo_period = self.cmo_period
        cmo_threshold = self.cmo_threshold
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Session_High = self.feat.max(high, timeperiod=range_period)
        Session_Low = self.feat.min(low, timeperiod=range_period)
        CMO = self.feat.cmo(close, timeperiod=cmo_period)
        TR = self.feat.trange(high, low, close)
        ATR_Filter = self.feat.atr(high, low, close, timeperiod=30)
        Midpoint = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > Session_High) & (CMO > cmo_threshold) & (TR > ATR_Filter)
        short_setup = (close < Session_Low) & (CMO < -cmo_threshold) & (TR > ATR_Filter)

        # 6. Exit logic
        exit_long = (close < Midpoint)
        exit_short = (close > Midpoint)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
