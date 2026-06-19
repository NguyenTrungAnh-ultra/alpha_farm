from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.tema_period = int(self.tema_period if 'tema_period' in self.__dict__ else 40)
        self.stochrsi_period = int(self.stochrsi_period if 'stochrsi_period' in self.__dict__ else 21)
        self.os_level = int(self.os_level if 'os_level' in self.__dict__ else 30)
        self.ob_level = int(self.ob_level if 'ob_level' in self.__dict__ else 70)
        self.donchian_exit_period = int(self.donchian_exit_period if 'donchian_exit_period' in self.__dict__ else 7)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.vol_filter_factor = float(self.vol_filter_factor if 'vol_filter_factor' in self.__dict__ else 0.85)
        tema_period = self.tema_period
        stochrsi_period = self.stochrsi_period
        os_level = self.os_level
        ob_level = self.ob_level
        donchian_exit_period = self.donchian_exit_period
        atr_period = self.atr_period
        vol_filter_factor = self.vol_filter_factor
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        tema = self.feat.tema(close, timeperiod=tema_period)
        tema_prev = self.op.shift(self.op, tema)
        stochrsi_k = self.feat.stochrsi(close, timeperiod=stochrsi_period, fastk_period=3, fastd_period=3)[0]
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)
        atr_ma = self.feat.sma(atr, timeperiod=20)
        donchian_low = LOWEST(low, donchian_exit_period)
        donchian_high = HIGHEST(high, donchian_exit_period)
        long_setup = (close > tema) & (tema > tema_prev) & (stochrsi_k < os_level) & (atr > vol_filter_factor * atr_ma)
        short_setup = (close < tema) & (tema < tema_prev) & (stochrsi_k > ob_level) & (atr > vol_filter_factor * atr_ma)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)