from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.adx_threshold = 25
        self.atr_exit_mult = 2.25

        # 2. Local variables for parameters
        adx_threshold = self.adx_threshold
        atr_exit_mult = self.atr_exit_mult

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        adx = self.feat.adx(high, low, close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        bullish_tasuki = self.feat.cdltasukigap(open_price, high, low, close) == 100
        bearish_tasuki = self.feat.cdltasukigap(open_price, high, low, close) == -100
        rolling_high_max = self.feat.max(high, timeperiod=10)
        rolling_low_min = self.feat.min(low, timeperiod=10)

        # 5. Entry logic
        long_setup = (bullish_tasuki) & (adx > adx_threshold)
        short_setup = (bearish_tasuki) & (adx > adx_threshold)

        # 6. Exit logic
        exit_long = close < (rolling_high_max - atr_exit_mult * atr)
        exit_short = close > (rolling_low_min + atr_exit_mult * atr)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
