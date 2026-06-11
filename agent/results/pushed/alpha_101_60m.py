class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        open_p = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        
        # Alpha 101: ((close - open) / ((high - low) + 0.001))
        alpha = (close - open_p) / ((high - low) + 0.001)
        
        # Normalize with Z-Score
        alpha_z = self.feat.rolling_zscore(alpha, window=60)
        
        # Set signal thresholds
        long_zone = alpha_z > 1.0
        short_zone = alpha_z < -1.0
        flat_zone = ~long_zone & ~short_zone
        
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)
