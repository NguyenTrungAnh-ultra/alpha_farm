from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.slope_trend_thresh = float(self.slope_trend_thresh if 'slope_trend_thresh' in self.__dict__ else 0.05)
        self.roc_mom_period = int(self.roc_mom_period if 'roc_mom_period' in self.__dict__ else 7)

        # 2. Local variables for parameters
        slope_trend_thresh = self.slope_trend_thresh
        roc_mom_period = self.roc_mom_period

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        slope_trend = self.feat.linearreg_slope(close, timeperiod=20)
        roc_mom = self.feat.roc(close, timeperiod=5)
        natr_vol = self.feat.natr(high, low, close, timeperiod=14)

        # 5. Entry logic
        long_setup = (slope_trend > 0.2) & (self.op.shift(roc_mom, -1)) <= roc_mom)
        short_setup = (slope_trend < -0.2) & ((self.op.shift(roc_mom, -1)) >= roc_mom)

        # 6. Exit logic
        exit_long = (natr_vol > natr_threshold * 1.5)
        exit_short = (natr_vol > natr_threshold * 1.5)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
