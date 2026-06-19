from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.adx_period = 15
        self.adx_threshold = 20
        self.cmo_period = 14
        self.cmo_threshold = 40
        self.exit_lookback = 14

        # 2. Local variables for parameters
        adx_period = self.adx_period
        adx_threshold = self.adx_threshold
        cmo_period = self.cmo_period
        cmo_threshold = self.cmo_threshold
        exit_lookback = self.exit_lookback

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        adx = self.feat.adx(high, low, close, timeperiod=adx_period)
        cmo = self.feat.cmo(close, timeperiod=cmo_period)
        kicking = self.feat.cdlkicking(open_price, high, low, close)
        minlow = self.feat.min(low, timeperiod=exit_lookback)
        maxhigh = self.feat.max(high, timeperiod=exit_lookback)

        # 5. Entry logic
        long_setup = (kicking == 100) & (cmo < -cmo_threshold) & (adx < adx_threshold)
        short_setup = (kicking == -100) & (cmo > cmo_threshold) & (adx < adx_threshold)

        # 6. Exit logic
        exit_long = close < minlow
        exit_short = close > maxhigh
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)


# OPTIMIZATION_V2_COMPLETED
