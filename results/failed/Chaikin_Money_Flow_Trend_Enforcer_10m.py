from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.cmf_period = 20
        self.cmf_entry_threshold = 0.175
        self.ema_fast = 11
        self.ema_slow = 30
        self.atr_period = 15
        self.min_atr_pct = 0.003

        # 2. Local variables for parameters
        cmf_period = self.cmf_period
        cmf_entry_threshold = self.cmf_entry_threshold
        ema_fast = self.ema_fast
        ema_slow = self.ema_slow
        atr_period = self.atr_period
        min_atr_pct = self.min_atr_pct

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        ad = self.feat.ad(high, low, close, volume)
        volume_sum = self.feat.sum(volume, timeperiod=cmf_period) + 1e-8
        cmf = (ad - self.op.shift(ad, cmf_period)) / volume_sum
        ema_fast = self.feat.ema(close, timeperiod=ema_fast)
        ema_slow = self.feat.ema(close, timeperiod=ema_slow)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)
        volatility_filter = atr / close > min_atr_pct

        # 5. Entry logic
        long_setup = (cmf > cmf_entry_threshold) & (close > ema_fast) & volatility_filter
        short_setup = (cmf < -cmf_entry_threshold) & (close < ema_fast) & volatility_filter

        # 6. Exit logic
        exit_long = (cmf < 0) | (close < ema_slow)
        exit_short = (cmf > 0) | (close > ema_slow)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)


# OPTIMIZATION_V2_COMPLETED
