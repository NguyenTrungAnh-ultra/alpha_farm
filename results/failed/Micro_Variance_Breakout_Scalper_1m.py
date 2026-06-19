from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.var_mult = 1.85
        self.vol_mult = 1.55
        self.atr_period = 10
        self.ema_trail_period = 12
        self.var_period = 6
        self.var_ema_period = 6

        # 2. Local variables for parameters
        var_mult = self.var_mult
        vol_mult = self.vol_mult
        atr_period = self.atr_period
        ema_trail_period = self.ema_trail_period
        var_period = self.var_period
        var_ema_period = self.var_ema_period

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        VAR_close = self.feat.var(close, timeperiod=5)
        VAR_ema = self.feat.ema(VAR_close, timeperiod=5)
        volume_sma = self.feat.sma(volume, timeperiod=10)
        ATR = self.feat.atr(high, low, close, timeperiod=7)
        EMA_trail = self.feat.ema(close, timeperiod=8)
        high_roll = self.feat.max(high, 3)
        low_roll = self.feat.min(low, 3)

        # 5. Entry logic
        long_setup = (close > high_roll) & (VAR_close > VAR_ema * 1.6) & (volume > volume_sma * 1.3)
        short_setup = (close < low_roll) & (VAR_close > VAR_ema * 1.6) & (volume > volume_sma * 1.3)

        # 6. Exit logic
        exit_long = (close < EMA_trail - 1.2 * ATR)
        exit_short = (close > EMA_trail + 1.2 * ATR)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
