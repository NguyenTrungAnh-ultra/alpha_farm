from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.kama_period = int(getattr(self, 'kama_period', 32))
        self.channel_period = int(getattr(self, 'channel_period', 21))
        self.adxr_threshold = float(getattr(self, 'adxr_threshold', 20.5))
        self.exit_period = int(getattr(self, 'exit_period', 16))

        # 2. Local variables for parameters
        kama_period = self.kama_period
        channel_period = self.channel_period
        adxr_threshold = self.adxr_threshold
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        KAMA = self.feat.kama(close, timeperiod=kama_period)
        Channel_High = self.feat.max(high, timeperiod=channel_period)
        Channel_Low = self.feat.min(low, timeperiod=channel_period)
        ADXR = self.feat.adxr(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midprice_Exit = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > Channel_High) & (close > KAMA) & (ADXR > adxr_threshold)
        short_setup = (close < Channel_Low) & (close < KAMA) & (ADXR > adxr_threshold)

        # 6. Exit logic
        exit_long = (close < Midprice_Exit - 0.5 * ATR) | (close < KAMA)
        exit_short = (close > Midprice_Exit + 0.5 * ATR) | (close > KAMA)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
