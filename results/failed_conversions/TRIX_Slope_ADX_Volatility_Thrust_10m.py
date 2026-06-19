from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.trix_period = int(self.trix_period if 'trix_period' in self.__dict__ else 20)
        self.adx_period = int(self.adx_period if 'adx_period' in self.__dict__ else 15)
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 22)
        self.slope_thresh = float(self.slope_thresh if 'slope_thresh' in self.__dict__ else 0.0105)
        self.exit_slope_thresh = float(self.exit_slope_thresh if 'exit_slope_thresh' in self.__dict__ else 0.016)
        self.atr_mult = float(self.atr_mult if 'atr_mult' in self.__dict__ else 2.0)
        trix_period = self.trix_period
        adx_period = self.adx_period
        bb_period = self.bb_period
        slope_thresh = self.slope_thresh
        exit_slope_thresh = self.exit_slope_thresh
        atr_mult = self.atr_mult
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        trix = self.feat.trix(close, timeperiod=trix_period)
        trix_slope = self.feat.linearreg_slope(self.feat.trix(close, timeperiod=trix_period), timeperiod=3)
        adx = self.feat.adx(high, low, close, timeperiod=adx_period)
        bb_width = (self.feat.bbands(close, timeperiod=bb_period, nbdevup=2, nbdevdn=2)[0] - self.feat.bbands(close, timeperiod=bb_period, nbdevup=2, nbdevdn=2)[2]) / self.feat.bbands(close, timeperiod=bb_period, nbdevup=2, nbdevdn=2)[1]
        ema20 = self.feat.ema(close, timeperiod=20)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        max_high_10 = self.feat.max(high, timeperiod=10)
        min_low_10 = self.feat.min(low, timeperiod=10)
        long_setup = (trix > 0) & (trix_slope > slope_thresh) & (adx > adx_thresh) & (bb_width > bb_thresh) & (close > ema20)
        short_setup = (trix < 0) & (trix_slope < -slope_thresh) & (adx > adx_thresh) & (bb_width > bb_thresh) & (close < ema20)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)