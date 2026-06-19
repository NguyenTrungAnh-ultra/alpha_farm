from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.ema_period = 20
        self.atr_period = 15
        self.vol_filter_mult = 0.55
        self.trail_mult = 2.25
        self.profit_mult = 3.0
        self.lookback_period = 6

        # 2. Local variables for parameters
        ema_period = self.ema_period
        atr_period = self.atr_period
        vol_filter_mult = self.vol_filter_mult
        trail_mult = self.trail_mult
        profit_mult = self.profit_mult
        lookback_period = self.lookback_period

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        ema_trend = self.feat.ema(close, timeperiod=20)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        atr_sma = self.feat.sma(atr, timeperiod=20)
        bullish_piercing = self.feat.cdlpiercing(open_price, high, low, close)
        bearish_darkcloud = self.feat.cdldarkcloudcover(open_price, high, low, close)
        highesthigh_5 = self.feat.max(high, timeperiod=5)
        lowestlow_5 = self.feat.min(low, timeperiod=5)

        # 5. Entry logic
        long_setup = (bullish_piercing > 0) & (close < ema_trend) & (atr > vol_filter_mult * atr_sma)
        short_setup = (bearish_darkcloud < 0) & (close > ema_trend) & (atr > vol_filter_mult * atr_sma)

        # 6. Exit logic
        exit_long = (close < highesthigh_5 - trail_mult * atr) | (close > ema_trend + profit_mult * atr)
        exit_short = (close > lowestlow_5 + trail_mult * atr) | (close < ema_trend - profit_mult * atr)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
