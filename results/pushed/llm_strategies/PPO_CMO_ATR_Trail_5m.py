from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):

    def __algorithm__(self):
        self.ppo_fast = 10
        self.ppo_slow = 59
        self.cmo_period = 60
        self.cmo_threshold = 21
        self.atr_period = 50
        self.atr_multiplier = 1.5
        self.trail_period = 100
        ppo_fast = self.ppo_fast
        ppo_slow = self.ppo_slow
        cmo_period = self.cmo_period
        cmo_threshold = self.cmo_threshold
        atr_period = self.atr_period
        atr_multiplier = self.atr_multiplier
        trail_period = self.trail_period
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        ppo = self.feat.ppo(close, fastperiod=12, slowperiod=26, matype=0)
        cmo = self.feat.cmo(close, timeperiod=14)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        highest_high = self.feat.max(high, timeperiod=20)
        lowest_low = self.feat.min(low, timeperiod=20)
        long_setup = (ppo > 0) & (cmo > 30)
        short_setup = (ppo < 0) & (cmo < -30)
        exit_long = close != close
        exit_short = close != close
        exit_setup = exit_long | exit_short
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

# OPTIMIZATION_V2_COMPLETED
