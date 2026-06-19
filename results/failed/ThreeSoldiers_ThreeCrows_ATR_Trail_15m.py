from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.ema_period = 45
        self.atr_period = 15
        self.atr_smoothing = 20
        self.trail_period = 22
        self.trail_multiplier = 3.25

        # 2. Local variables for parameters
        ema_period = self.ema_period
        atr_period = self.atr_period
        atr_smoothing = self.atr_smoothing
        trail_period = self.trail_period
        trail_multiplier = self.trail_multiplier

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        EMA_trend = self.feat.ema(close, timeperiod=50)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        ATR_ma = self.feat.sma(ATR, timeperiod=20)
        chandelier_long_stop = self.feat.max(high, 22) - ATR * 3.0
        chandelier_short_stop = self.feat.min(low, 22) + ATR * 3.0
        bullish_pattern = self.feat.three_white_soldiers(open_price, high, low, close)
        bearish_pattern = self.feat.three_black_crows(open_price, high, low, close)

        # 5. Entry logic
        long_setup = (bullish_pattern > 0) & (close > EMA_trend) & (ATR > ATR_ma)
        short_setup = (bearish_pattern < 0) & (close < EMA_trend) & (ATR > ATR_ma)

        # 6. Exit logic
        exit_long = (close < chandelier_long_stop)
        exit_short = (close > chandelier_short_stop)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
