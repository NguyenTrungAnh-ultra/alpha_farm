# [MCTS_DISCOVERY_ENGINE]
from core_engine.XnoEngine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Inputs
        open_price = self.data.pv_open
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        
        # 2. Discovered Core Formula
        alpha_val = (self.feat.zscore(self.feat.zscore((self.op.diff(self.feat.macd(low)[0], periods=2) / (self.feat.stddev(self.feat.ema(self.feat.hammer(open_, high, low, close), timeperiod=30), timeperiod=14) + 1e-8)), timeperiod=14), timeperiod=14) > 1.0)
        
        # 3. Standardization (Z-Score)
        window = 14
        r_mean = self.feat.rolling_mean(alpha_val, window)
        r_std = self.feat.rolling_std(alpha_val, window) + 1e-8
        
        z_score = (alpha_val - r_mean) / r_std
        z_score = z_score * 1.0

        # 4. Position signals (EXIT first, ENTRY second)
        raw_pos = self.op.where(z_score > 0.5, 0.3, self.op.where(z_score < -0.5, -0.3, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == 0.3
        short_mask = raw_pos == -0.3
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position=0.3)
        self.set_positions(short_mask, position=-0.3)
