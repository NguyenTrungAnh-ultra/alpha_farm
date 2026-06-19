from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.variance_period = 20
        self.squeeze_buffer = 0.275
        self.adx_period = 15
        self.adx_threshold = 25
        self.donchian_period = 20
        self.atr_period = 15
        self.atr_multiplier = 2.25
        self.trailing_period = 10

        # 2. Local variables for parameters
        variance_period = self.variance_period
        squeeze_buffer = self.squeeze_buffer
        adx_period = self.adx_period
        adx_threshold = self.adx_threshold
        donchian_period = self.donchian_period
        atr_period = self.atr_period
        atr_multiplier = self.atr_multiplier
        trailing_period = self.trailing_period

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        typical_price = (high + low + close) / 3
        variance = self.feat.var(typical_price, timeperiod=20)
        variance_min = self.feat.min(variance, timeperiod=20)
        squeeze = variance <= variance_min * (1 + 0.2)
        ADX = self.feat.adx(high, low, close, timeperiod=14)
        Donchian_high = self.feat.max(high, timeperiod=20)
        Donchian_low = self.feat.min(low, timeperiod=20)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        trailing_high = self.feat.max(high, timeperiod=10)
        trailing_low = self.feat.min(low, timeperiod=10)

        # 5. Entry logic
        long_setup = (close > Donchian_high) & (squeeze) & (ADX > 25)
        short_setup = (close < Donchian_low) & (squeeze) & (ADX > 25)

        # 6. Exit logic
        exit_long = close < (trailing_high - 2.0 * ATR)
        exit_short = close > (trailing_low + 2.0 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
