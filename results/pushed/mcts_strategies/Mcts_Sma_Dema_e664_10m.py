# [MCTS_DISCOVERY_ENGINE]
from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        
        # 2. Discovered Core Formula
        alpha_val = self.feat.sma(self.feat.dema(self.feat.dema(self.feat.atr(high, low, close, timeperiod=30), timeperiod=10), timeperiod=5), timeperiod=10)
        
        # 3. Standardization
        window = 120
        r_min = self.feat.rolling_min(alpha_val, window)
        r_max = self.feat.rolling_max(alpha_val, window)
        scaled = (alpha_val - r_min) / (r_max - r_min + 1e-8)
        scaled = (scaled - 0.5) * 2.0
        
        # Direction
        scaled = scaled * -1.0
        
        # 4. Position signals (EXIT first, ENTRY second)
        raw_pos = self.op.where(scaled > 0.5, 0.2, self.op.where(scaled < -0.5, -0.2, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == 0.2
        short_mask = raw_pos == -0.2
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position=0.2)
        self.set_positions(short_mask, position=-0.2)
