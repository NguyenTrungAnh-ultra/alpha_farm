class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # Parameters
        self.basis_window = 21
        self.bb_period = 20
        self.bb_std = 1.8
        self.rsi_period = 13
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        
        # Core variables
        close = self.data.pv_close
        vol = self.data.pv_volume
        vn30_close = self.data.pv_vn30_close
        
        # 1. Basis & Z-Score
        basis = close - vn30_close
        basis_zscore = self.feat.rolling_zscore(basis, self.basis_window)
        
        # 2. Bollinger Bands
        bb_mid = self.feat.sma(close, self.bb_period)
        bb_std_val = self.feat.rolling_std(close, self.bb_period)
        bb_upper = bb_mid + self.bb_std * bb_std_val
        bb_lower = bb_mid - self.bb_std * bb_std_val
        
        # 3. RSI
        rsi = self.feat.rsi(close, self.rsi_period)
        
        # 4. Entry Logic (Strict Re-entry & Volume Filter)
        # Long when Basis is deeply negative (VN30F undervalued vs VN30)
        long_setup = (
            (basis_zscore < -2.0) & 
            (self.op.shift(close, 1) < self.op.shift(bb_lower, 1)) & 
            (close > bb_lower) & 
            (rsi < self.rsi_oversold) & 
            (vol > 0)
        )
        
        # Short when Basis is deeply positive (VN30F overvalued vs VN30)
        short_setup = (
            (basis_zscore > 2.0) & 
            (self.op.shift(close, 1) > self.op.shift(bb_upper, 1)) & 
            (close < bb_upper) & 
            (rsi > self.rsi_overbought) & 
            (vol > 0)
        )
        
        # 5. Exit Logic (Neutral Zone Exit)
        # Exit when Basis mean reverts to neutral territory
        flat_zone = ((basis_zscore > -0.5) & (basis_zscore < 0.5)) | (vol == 0)
        
        # 6. Execute Orders
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)

