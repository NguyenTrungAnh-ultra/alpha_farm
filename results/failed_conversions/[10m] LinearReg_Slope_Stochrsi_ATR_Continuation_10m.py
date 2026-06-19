from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.slope_threshold = float(self.slope_threshold if 'slope_threshold' in self.__dict__ else 1.05)
        self.stochrsi_overbought = float(self.stochrsi_overbought if 'stochrsi_overbought' in self.__dict__ else 87.5)

        # 2. Local variables for parameters
        slope_threshold = self.slope_threshold
        stochrsi_overbought = self.stochrsi_overbought

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        ema_fast = self.feat.ema(close, timeperiod=20)
        slope = self.feat.linearreg_slope(open_price, close, timeperiod=14)
        stochrsi = self.feat.stochrsi(close, k1=5, l2=3)}
        atr = self.feat.atr(high, low, close, timeperiod=14)

        # 5. Entry logic
        long_setup = (close > ema_fast) & (slope > 0.0) & (stochrsi < Stochrsi_threshold)
        short_setup = (close < ema_fast) & (slope < -0.5) & (stochrsi > Stochrsi_overbought)

        # 6. Exit logic
        exit_long = (close < ema_fast) | (slope <= 0.0)
        exit_short = (close > ema_fast) | (slope >= -0.5)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
