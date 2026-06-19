from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.adx_threshold = 25
        self.atr_multiplier = 2.25
        self.ema_period = 22
        self.trailing_lookback = 10

        # 2. Local variables for parameters
        adx_threshold = self.adx_threshold
        atr_multiplier = self.atr_multiplier
        ema_period = self.ema_period
        trailing_lookback = self.trailing_lookback

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        ema_trend = self.feat.ema(close, timeperiod=20)
        adx = self.feat.adx(high, low, close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        dragonfly = self.feat.cdldragonflydoji(open_price, high, low, close)
        gravestone = self.feat.cdlgravestonedoji(open_price, high, low, close)
        highesthigh = self.feat.max(high, timeperiod=10)
        lowestlow = self.feat.min(low, timeperiod=10)

        # 5. Entry logic
        long_setup = (dragonfly == 100) & (close < ema_trend) & (adx > 25)
        short_setup = (gravestone == -100) & (close > ema_trend) & (adx > 25)

        # 6. Exit logic
        exit_long = close < (highesthigh - 2.0 * atr)
        exit_short = close > (lowestlow + 2.0 * atr)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
