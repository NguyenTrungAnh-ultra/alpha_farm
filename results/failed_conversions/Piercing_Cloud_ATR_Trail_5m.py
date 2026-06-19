from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ema_period = int(self.ema_period if 'ema_period' in self.__dict__ else 20)
        self.atr_period = int(self.atr_period if 'atr_period' in self.__dict__ else 15)
        self.vol_filter_mult = float(self.vol_filter_mult if 'vol_filter_mult' in self.__dict__ else 0.55)
        self.trail_mult = float(self.trail_mult if 'trail_mult' in self.__dict__ else 2.25)
        self.profit_mult = float(self.profit_mult if 'profit_mult' in self.__dict__ else 3.0)
        self.lookback_period = int(self.lookback_period if 'lookback_period' in self.__dict__ else 6)
        ema_period = self.ema_period
        atr_period = self.atr_period
        vol_filter_mult = self.vol_filter_mult
        trail_mult = self.trail_mult
        profit_mult = self.profit_mult
        lookback_period = self.lookback_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ema_trend = self.feat.ema(close, timeperiod=20)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        atr_sma = self.feat.sma(atr, timeperiod=20)
        bullish_piercing = self.feat.piercing_pattern(open_price, high, low, close)
        bearish_darkcloud = darkcloudcover_pattern(open_price, high, low, close)
        highesthigh_5 = self.feat.max(high, timeperiod=5)
        lowestlow_5 = self.feat.min(low, timeperiod=5)
        long_setup = (bullish_piercing > 0) & (close < ema_trend) & (atr > vol_filter_mult * atr_sma)
        short_setup = (bearish_darkcloud < 0) & (close > ema_trend) & (atr > vol_filter_mult * atr_sma)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)