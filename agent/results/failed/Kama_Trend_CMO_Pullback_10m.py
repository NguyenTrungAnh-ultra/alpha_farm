from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.kama_period = int(getattr(self, 'kama_period', 30))
        self.cmo_period = int(getattr(self, 'cmo_period', 12))
        self.cmo_long_pullback = float(getattr(self, 'cmo_long_pullback', -2.5))
        self.cmo_short_pullback = float(getattr(self, 'cmo_short_pullback', 2.5))
        self.adx_threshold = float(getattr(self, 'adx_threshold', 23.0))
        self.exit_period = int(getattr(self, 'exit_period', 17))

        # 2. Local variables for parameters
        kama_period = self.kama_period
        cmo_period = self.cmo_period
        cmo_long_pullback = self.cmo_long_pullback
        cmo_short_pullback = self.cmo_short_pullback
        adx_threshold = self.adx_threshold
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        KAMA = self.feat.kama(close, timeperiod=kama_period)
        CMO = self.feat.cmo(close, timeperiod=cmo_period)
        ADX = self.feat.adx(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midprice = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > KAMA) & (CMO < cmo_long_pullback) & (ADX > adx_threshold)
        short_setup = (close < KAMA) & (CMO > cmo_short_pullback) & (ADX > adx_threshold)

        # 6. Exit logic
        exit_long = (close < Midprice - 0.5 * ATR)
        exit_short = (close > Midprice + 0.5 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
