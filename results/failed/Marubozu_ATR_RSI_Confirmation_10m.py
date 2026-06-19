from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.EMA_period = 25
        self.ATR_period = 20
        self.atr_multiplier = 2.0
        self.rsi_exit_upper = 77
        self.rsi_exit_lower = 22

        # 2. Local variables for parameters
        EMA_period = self.EMA_period
        ATR_period = self.ATR_period
        atr_multiplier = self.atr_multiplier
        rsi_exit_upper = self.rsi_exit_upper
        rsi_exit_lower = self.rsi_exit_lower

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        marubozu = self.feat.cdlmarubozu(open_price, high, low, close)
        ema_fast = self.feat.ema(close, timeperiod=EMA_period)
        rsi = self.feat.rsi(close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=ATR_period)

        # 5. Entry logic
        long_setup = (marubozu == 100) & (rsi > 50) & (close > ema_fast)
        short_setup = (marubozu == -100) & (rsi < 50) & (close < ema_fast)

        # 6. Exit logic
        exit_long = (rsi > rsi_exit_upper) | (close < (ema_fast - atr_multiplier * atr))
        exit_short = (rsi < rsi_exit_lower) | (close > (ema_fast + atr_multiplier * atr))
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)


# OPTIMIZATION_V2_COMPLETED
