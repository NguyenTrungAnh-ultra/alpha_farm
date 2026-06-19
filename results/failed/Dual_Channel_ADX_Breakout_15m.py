from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.bb_period = 22
        self.bb_std = 2.0
        self.kc_mult = 1.5
        self.adx_period = 15
        self.adx_threshold = 20

        # 2. Local variables for parameters
        bb_period = self.bb_period
        bb_std = self.bb_std
        kc_mult = self.kc_mult
        adx_period = self.adx_period
        adx_threshold = self.adx_threshold

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        bb_upper = self.feat.bbands(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)[0]
        bb_middle = self.feat.bbands(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)[1]
        bb_lower = self.feat.bbands(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)[2]
        atr = self.feat.atr(high, low, close, timeperiod=20)
        kc_upper = bb_middle + 1.5 * atr
        kc_middle = bb_middle
        kc_lower = bb_middle - 1.5 * atr
        adx = self.feat.adx(high, low, close, timeperiod=14)

        # 5. Entry logic
        long_setup = (close > bb_upper) & (close > kc_upper) & (adx > 20)
        short_setup = (close < bb_lower) & (close < kc_lower) & (adx > 20)

        # 6. Exit logic
        exit_long = (close < bb_middle) | (close < kc_middle)
        exit_short = (close > bb_middle) | (close > kc_middle)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
