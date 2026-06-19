from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.tema_period = int(self.tema_period if 'tema_period' in self.__dict__ else 9)
        self.ad_sma_period = int(self.ad_sma_period if 'ad_sma_period' in self.__dict__ else 12)
        self.vol_ratio_threshold = float(self.vol_ratio_threshold if 'vol_ratio_threshold' in self.__dict__ else 0.825)
        self.ad_long_mult = float(self.ad_long_mult if 'ad_long_mult' in self.__dict__ else 1.06)
        self.ad_short_mult = float(self.ad_short_mult if 'ad_short_mult' in self.__dict__ else 0.94)

        # 2. Local variables for parameters
        tema_period = self.tema_period
        ad_sma_period = self.ad_sma_period
        vol_ratio_threshold = self.vol_ratio_threshold
        ad_long_mult = self.ad_long_mult
        ad_short_mult = self.ad_short_mult

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        tema = self.feat.tema(close, timeperiod=tema_period)
        ad = IF (high - low == 0) THEN 0 ELSE ((close - low) - (high - close)) / (high - low + 1e-8) * volume
        ad_sma = self.feat.sma(ad, timeperiod=ad_sma_period)
        atr_fast = self.feat.atr(high, low, close, timeperiod=14)
        atr_slow = self.feat.atr(high, low, close, timeperiod=28)
        vol_contraction = atr_fast / (atr_slow + 1e-8) < vol_ratio_threshold

        # 5. Entry logic
        long_setup = (close > tema) & (ad > ad_sma * ad_long_mult) & vol_contraction
        short_setup = (close < tema) & (ad < ad_sma * ad_short_mult) & vol_contraction

        # 6. Exit logic
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
