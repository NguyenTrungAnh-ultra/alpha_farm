from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.ema_period = 20
        self.atr_period = 15
        self.sma_atr_period = 50
        self.atr_min_mult = 1.25
        self.exit_atr_mult = 2.0

        # 2. Local variables for parameters
        ema_period = self.ema_period
        atr_period = self.atr_period
        sma_atr_period = self.sma_atr_period
        atr_min_mult = self.atr_min_mult
        exit_atr_mult = self.exit_atr_mult

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        harami = self.feat.cdlharami(open_price, high, low, close)
        ema_trend = self.feat.ema(close, ema_period)
        atr_val = self.feat.atr(high, low, close, atr_period)
        atr_sma = self.feat.sma(atr_val, sma_atr_period)

        # 5. Entry logic
        long_setup = (harami == 100) & (close > ema_trend) & (atr_val > atr_min_mult * atr_sma)
        short_setup = (harami == -100) & (close < ema_trend) & (atr_val > atr_min_mult * atr_sma)

        # 6. Exit logic
        exit_long = (close < (ema_trend - exit_atr_mult * atr_val)) | (harami == -100)
        exit_short = (close > (ema_trend + exit_atr_mult * atr_val)) | (harami == 100)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
