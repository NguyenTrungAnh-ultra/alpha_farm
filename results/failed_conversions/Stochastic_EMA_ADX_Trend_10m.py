from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold = float(self.adx_threshold if 'adx_threshold' in self.__dict__ else 22.5)
        self.stochrsi_k_period = int(self.stochrsi_k_period if 'stochrsi_k_period' in self.__dict__ else 16)
        adx_threshold = self.adx_threshold
        stochrsi_k_period = self.stochrsi_k_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_fast = self.feat.ema(close, timeperiod=20)
        stochrsi = self.feat.stochrsi(high, low, close, fast_k_period=14, slow_d_period=3)[0]
        adx_signal = self.feat.adx(close, high, low, timeperiod=14)
        long_setup = self.op.crossed_above(stochrsi, 50) & (close > ema_fast)
        short_setup = self.op.crossed_below(stochrsi, 50) & (close < ema_fast)
        exit_long = ema_crosses_below(ema_fast, timeperiod=21) | (close < ema_fast)
        exit_short = ema_crosses_above(ema_fast, timeperiod=21) | (close > ema_fast)
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)