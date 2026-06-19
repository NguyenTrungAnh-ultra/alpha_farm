from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 30)
        self.stochf_k = float(self.stochf_k if 'stochf_k' in self.__dict__ else 6.0)

        # 2. Local variables for parameters
        ema_period = self.ema_period
        stochf_k = self.stochf_k

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        ema_fast = self.feat.ema(close, timeperiod=20)
        stochf = self.feat.stochf(high, low, close)}
        sma_slow = self.feat.sma(close, timeperiod=50)

        # 5. Entry logic
        long_setup = (close > ema_fast) & (stochf < lower_limit)
        short_setup = (close < sma_slow) & (stochf > upper_limit)

        # 6. Exit logic
        exit_long = (close <= ema_fast)
        exit_short = (close >= sma_slow)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
