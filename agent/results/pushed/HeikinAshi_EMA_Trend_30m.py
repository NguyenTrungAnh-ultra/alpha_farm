from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # Parameters
        self.ema_short_period = 10
        self.ema_long_period = 30
        self.shadow_tolerance = 0.5  # VN30 points tolerance for "no shadow"
        
        # Raw Data
        open_p = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        
        # 1. Vectorized Heikin-Ashi Approximation
        # HA Close
        ha_close = (open_p + high + low + close) / 4.0
        
        # HA Open (Approximation: prev_open + prev_close / 2)
        prev_open = self.op.shift(open_p, 1)
        prev_close = self.op.shift(close, 1)
        ha_open = (prev_open + prev_close) / 2.0
        
        # HA High
        temp_high = self.op.where(high > ha_open, high, ha_open)
        ha_high = self.op.where(temp_high > ha_close, temp_high, ha_close)
        
        # HA Low
        temp_low = self.op.where(low < ha_open, low, ha_open)
        ha_low = self.op.where(temp_low < ha_close, temp_low, ha_close)
        
        # 2. Trend & Momentum Indicators
        ema_short = self.feat.ema(ha_close, self.ema_short_period)
        ema_long = self.feat.ema(ha_close, self.ema_long_period)
        
        # 3. No Shadow Filter
        # No lower shadow means uptrend
        no_lower_shadow = (ha_open - ha_low) <= self.shadow_tolerance
        # No upper shadow means downtrend
        no_upper_shadow = (ha_high - ha_open) <= self.shadow_tolerance
        
        # 4. Entry Logic
        long_setup = (ema_short > ema_long) & no_lower_shadow
        short_setup = (ema_short < ema_long) & no_upper_shadow
        
        # 5. Exit Logic (Simple Trend Reversal)
        exit_long = ema_short < ema_long
        exit_short = ema_short > ema_long
        flat_zone = exit_long | exit_short
        
        # 6. Execute Orders
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
