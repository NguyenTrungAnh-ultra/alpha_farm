from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.adx_period = 15
        self.rsi_period = 15
        self.atr_period = 15
        self.stop_multiplier = 2.25
        self.rsi_exit_level = 50
        self.lookback = 10

        # 2. Local variables for parameters
        adx_period = self.adx_period
        rsi_period = self.rsi_period
        atr_period = self.atr_period
        stop_multiplier = self.stop_multiplier
        rsi_exit_level = self.rsi_exit_level
        lookback = self.lookback

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        adx = self.feat.adx(high, low, close, timeperiod=14)
        rsi = self.feat.rsi(close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        ladderbottom = self.feat.cdlladderbottom(open_price, high, low, close)
        laddertop = self.feat.cdlladderbottom(open_price, high, low, close)
        highesthigh = self.feat.rolling_max(high, 10)
        lowestlow = self.feat.rolling_min(low, 10)

        # 5. Entry logic
        long_setup = (ladderbottom > 0) & (adx < 20) & (rsi < 30)
        short_setup = (laddertop > 0) & (adx < 20) & (rsi > 70)

        # 6. Exit logic
        exit_long = (close < (highesthigh - stop_multiplier * atr)) | (rsi > rsi_exit_level)
        exit_short = (close > (lowestlow + stop_multiplier * atr)) | (rsi < rsi_exit_level)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
