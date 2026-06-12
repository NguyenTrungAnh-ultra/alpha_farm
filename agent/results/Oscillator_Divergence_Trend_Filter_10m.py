from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.trend_period = int(getattr(self, 'trend_period', 31))
        self.adx_min = float(getattr(self, 'adx_min', 24.5))
        self.stoch_period = int(getattr(self, 'stoch_period', 11))
        self.oversold_bound = float(getattr(self, 'oversold_bound', 30.0))
        self.overbought_bound = float(getattr(self, 'overbought_bound', 62.0))

        # 2. Local variables for parameters
        trend_period = self.trend_period
        adx_min = self.adx_min
        stoch_period = self.stoch_period
        oversold_bound = self.oversold_bound
        overbought_bound = self.overbought_bound

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        DEMA_trend = self.feat.dema(close, timeperiod=trend_period)
        ADX = self.feat.adx(high, low, close, timeperiod=14)
        Stoch_K = self.feat.stoch(high, low, close, fastk_period=stoch_period, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)[0]
        Stoch_D = self.feat.stoch(high, low, close, fastk_period=stoch_period, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)[1]
        BB_Mid = self.feat.bbands(close, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)[1]
        StdDev = self.feat.stddev(close, timeperiod=20)

        # 5. Entry logic
        long_setup = (close > DEMA_trend) & (ADX > adx_min) & (Stoch_K > Stoch_D) & (Stoch_D < oversold_bound)
        short_setup = (close < DEMA_trend) & (ADX > adx_min) & (Stoch_K < Stoch_D) & (Stoch_D > overbought_bound)

        # 6. Exit logic
        exit_long = (close < BB_Mid - 0.5 * StdDev)
        exit_short = (close > BB_Mid + 0.5 * StdDev)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
