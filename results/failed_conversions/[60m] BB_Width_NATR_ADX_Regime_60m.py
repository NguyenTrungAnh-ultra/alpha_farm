from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.adx_threshold_low = int(self.adx_threshold_low if 'adx_threshold_low' in self.__dict__ else 27)
        self.ema_period_wide = int(self.ema_period_wide if 'ema_period_wide' in self.__dict__ else 37)
        adx_threshold_low = self.adx_threshold_low
        ema_period_wide = self.ema_period_wide
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        bb_width = self.feat.bbands.upper - self.feat.bbands.lower
        ema_bbwid = self.feat.ema(self.indicators[0], timeperiod=20)
        natr = self.feat.natr(high, low, close, timeperiod=14)
        adx = self.feat.adx(close, high, low, volume, timeperiod=14)
        long_setup = (bb_width > ema_bbwid) & (natr > self.indicators[2]) & (adx > 20)
        short_setup = (close < bb_width - ema_bbwid) & (natr > self.indicators[3]) & (adx > 15)
        exit_long = (bb_width < ema_bbwid) | (natr < self.feat.ema(natr))
        exit_short = (close > bbands.upper) | (natr < self.feat.ema(natr))
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)