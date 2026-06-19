from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.tema_period = int(self.tema_period if 'tema_period' in self.__dict__ else 20)
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 20)
        self.bb_std = float(self.bb_std if 'bb_std' in self.__dict__ else 2.0)
        self.adx_period = int(self.adx_period if 'adx_period' in self.__dict__ else 15)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.trail_lookback = int(self.trail_lookback if 'trail_lookback' in self.__dict__ else 10)
        self.trail_multiplier = float(self.trail_multiplier if 'trail_multiplier' in self.__dict__ else 2.25)
        self.oversold_thresh = float(self.oversold_thresh if 'oversold_thresh' in self.__dict__ else 0.2)
        self.overbought_thresh = float(self.overbought_thresh if 'overbought_thresh' in self.__dict__ else 0.8)
        self.adx_min = int(self.adx_min if 'adx_min' in self.__dict__ else 22)
        tema_period = self.tema_period
        bb_period = self.bb_period
        bb_std = self.bb_std
        adx_period = self.adx_period
        atr_period = self.atr_period
        trail_lookback = self.trail_lookback
        trail_multiplier = self.trail_multiplier
        oversold_thresh = self.oversold_thresh
        overbought_thresh = self.overbought_thresh
        adx_min = self.adx_min
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        tema = self.feat.tema(close, timeperiod=tema_period)
        tema_prev = self.op.shift(self.op, tema)
        upperbb = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_std, nbdevdn=bb_std, matype=0)[0]
        lowerbb = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_std, nbdevdn=bb_std, matype=0)[2]
        percentb = (close - lowerbb) / (upperbb - lowerbb + 1e-08)
        adx = self.feat.adx(high, low, close, timeperiod=adx_period)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)
        trail_max_high = rolling_max(high, trail_lookback)
        trail_min_low = rolling_min(low, trail_lookback)
        long_setup = (tema > tema_prev) & (percentb < oversold_thresh) & (adx > adx_min)
        short_setup = (tema < tema_prev) & (percentb > overbought_thresh) & (adx > adx_min)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)