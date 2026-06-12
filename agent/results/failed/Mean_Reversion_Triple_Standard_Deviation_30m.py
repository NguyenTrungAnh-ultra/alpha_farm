from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.bb_period = int(getattr(self, 'bb_period', 37))
        self.bb_mult = float(getattr(self, 'bb_mult', 2.7))
        self.rsi_period = int(getattr(self, 'rsi_period', 15))
        self.rsi_lower = float(getattr(self, 'rsi_lower', 27.5))
        self.rsi_upper = float(getattr(self, 'rsi_upper', 72.5))
        self.aroon_period = int(getattr(self, 'aroon_period', 30))

        # 2. Local variables for parameters
        bb_period = self.bb_period
        bb_mult = self.bb_mult
        rsi_period = self.rsi_period
        rsi_lower = self.rsi_lower
        rsi_upper = self.rsi_upper
        aroon_period = self.aroon_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        BB_Upper = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_mult, nbdevdn=bb_mult)[0]
        BB_Lower = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_mult, nbdevdn=bb_mult)[2]
        Midpoint = self.feat.midpoint(close, timeperiod=bb_period)
        RSI = self.feat.rsi(close, timeperiod=rsi_period)
        Aroon_Osc = self.feat.aroonosc(high, low, timeperiod=aroon_period)
        ATR = self.feat.atr(high, low, close, timeperiod=14)

        # 5. Entry logic
        long_setup = (Aroon_Osc > -70) & (Aroon_Osc < 70) & (RSI < rsi_lower) & (close < BB_Lower)
        short_setup = (Aroon_Osc > -70) & (Aroon_Osc < 70) & (RSI > rsi_upper) & (close > BB_Upper)

        # 6. Exit logic
        exit_long = (close > Midpoint) | (close < BB_Lower - 1.5 * ATR)
        exit_short = (close < Midpoint) | (close > BB_Upper + 1.5 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
