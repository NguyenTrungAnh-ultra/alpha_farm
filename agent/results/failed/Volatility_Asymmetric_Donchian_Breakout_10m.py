from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.breakout_period = int(getattr(self, 'breakout_period', 25))
        self.expansion_factor = float(getattr(self, 'expansion_factor', 1.45))
        self.exit_period = int(getattr(self, 'exit_period', 17))

        # 2. Local variables for parameters
        breakout_period = self.breakout_period
        expansion_factor = self.expansion_factor
        exit_period = self.exit_period

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Upper_Band = self.feat.max(high, timeperiod=breakout_period)
        Lower_Band = self.feat.min(low, timeperiod=breakout_period)
        Volatility_Fast = self.feat.stddev(close, timeperiod=10)
        Volatility_Slow = self.feat.sma(self.feat.stddev(close, timeperiod=10), timeperiod=30)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midprice_Exit = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > Upper_Band) & (Volatility_Fast > Volatility_Slow * expansion_factor)
        short_setup = (close < Lower_Band) & (Volatility_Fast > Volatility_Slow * expansion_factor)

        # 6. Exit logic
        exit_long = (close < Midprice_Exit - 0.25 * ATR)
        exit_short = (close > Midprice_Exit + 0.25 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
