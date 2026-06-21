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
        alpha_val = (self.feat.zscore(self.feat.zscore((self.op.diff(self.feat.macd(open_)[0], periods=3) / (self.feat.vwap(high, low, close, volume) + 1e-8)), timeperiod=60), timeperiod=20) > 2.5)
        
        # 3. Standardization (Z-Score)
        window = 60
        r_mean = self.feat.rolling_mean(alpha_val, window)
        r_std = self.feat.rolling_std(alpha_val, window) + 1e-8
        
        z_score = (alpha_val - r_mean) / r_std
        z_score = z_score * 1.0

        # 4. Position signals (EXIT first, ENTRY second)
        raw_pos = self.op.where(z_score > 0.5, 0.2, self.op.where(z_score < -0.5, -0.2, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == 0.2
        short_mask = raw_pos == -0.2
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position=0.2)
        self.set_positions(short_mask, position=-0.2)
