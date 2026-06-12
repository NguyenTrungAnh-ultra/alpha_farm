from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.bb_period = int(getattr(self, 'bb_period', 20))
        self.bb_mult = float(getattr(self, 'bb_mult', 2.15))
        self.squeeze_threshold = float(getattr(self, 'squeeze_threshold', 0.015))
        self.oversold_bound = float(getattr(self, 'oversold_bound', 30.0))
        self.overbought_bound = float(getattr(self, 'overbought_bound', 70.0))
        self.exit_period = int(getattr(self, 'exit_period', 15))

        # 2. Local variables for parameters
        bb_period = self.bb_period
        bb_mult = self.bb_mult
        squeeze_threshold = self.squeeze_threshold
        oversold_bound = self.oversold_bound
        overbought_bound = self.overbought_bound
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        BB_Upper = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_mult, nbdevdn=bb_mult)[0]
        BB_Lower = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_mult, nbdevdn=bb_mult)[2]
        BB_Bandwidth = (BB_Upper - BB_Lower) / (self.feat.midpoint(close, timeperiod=bb_period) + 1e-8)
        ULTOSC = self.feat.ultosc(high, low, close, timeperiod1=7, timeperiod2=14, timeperiod3=28)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midprice_Exit = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (BB_Bandwidth < squeeze_threshold) & (ULTOSC < oversold_bound) & (close < BB_Lower)
        short_setup = (BB_Bandwidth < squeeze_threshold) & (ULTOSC > overbought_bound) & (close > BB_Upper)

        # 6. Exit logic
        exit_long = (close > Midprice_Exit) | (close < BB_Lower - 1.0 * ATR)
        exit_short = (close < Midprice_Exit) | (close > BB_Upper + 1.0 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
