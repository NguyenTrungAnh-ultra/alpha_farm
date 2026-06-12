from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.bb_period = int(getattr(self, 'bb_period', 16))
        self.bb_mult = float(getattr(self, 'bb_mult', 2.4))
        self.kc_mult = float(getattr(self, 'kc_mult', 1.9))
        self.kama_period = int(getattr(self, 'kama_period', 42))
        self.sar_acc = float(getattr(self, 'sar_acc', 0.04))
        self.sar_max = float(getattr(self, 'sar_max', 0.1))

        # 2. Local variables for parameters
        bb_period = self.bb_period
        bb_mult = self.bb_mult
        kc_mult = self.kc_mult
        kama_period = self.kama_period
        sar_acc = self.sar_acc
        sar_max = self.sar_max

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        BB_Upper = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_mult, nbdevdn=bb_mult)[0]
        BB_Lower = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_mult, nbdevdn=bb_mult)[2]
        EMA_mid = self.feat.ema(close, timeperiod=bb_period)
        ATR = self.feat.atr(high, low, close, timeperiod=bb_period)
        KC_Upper = EMA_mid + (kc_mult * ATR)
        KC_Lower = EMA_mid - (kc_mult * ATR)
        Squeeze_Active = ((BB_Upper - BB_Lower) < (KC_Upper - KC_Lower))
        KAMA = self.feat.kama(close, timeperiod=kama_period)
        SAR = self.feat.sar(high, low, acceleration=sar_acc, maximum=sar_max)

        # 5. Entry logic
        long_setup = (Squeeze_Active == 0) & (close > KAMA) & (close > SAR)
        short_setup = (Squeeze_Active == 0) & (close < KAMA) & (close < SAR)

        # 6. Exit logic
        exit_long = (close < SAR)
        exit_short = (close > SAR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
