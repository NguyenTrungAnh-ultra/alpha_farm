from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Dữ liệu giá
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        open_ = self.data.pv_open
        volume = self.data.pv_volume
        
        # Returns
        returns = self.feat.returns(close, 1)
        
        # Cap proxy
        cap = close * 1e6
        
        # VWAP proxy
        vwap = self.feat.rolling_mean(close, 20)
        
        # ADV variables
        adv5 = self.feat.rolling_mean(volume, 5)
        adv10 = self.feat.rolling_mean(volume, 10)
        adv15 = self.feat.rolling_mean(volume, 15)
        adv20 = self.feat.rolling_mean(volume, 20)
        adv30 = self.feat.rolling_mean(volume, 30)
        adv40 = self.feat.rolling_mean(volume, 40)
        adv50 = self.feat.rolling_mean(volume, 50)
        adv60 = self.feat.rolling_mean(volume, 60)
        adv81 = self.feat.rolling_mean(volume, 81)
        adv120 = self.feat.rolling_mean(volume, 120)
        adv150 = self.feat.rolling_mean(volume, 150)
        adv180 = self.feat.rolling_mean(volume, 180)
        
        # 2. Tính toán giá trị Alpha thô (inline)

        rank_minus = self.feat.rolling_rank(vwap - close, 20)
        rank_plus = self.feat.rolling_rank(vwap + close, 20)
        rank_plus_safe = self.op.where(rank_plus > 0.001, rank_plus, 0.001)
        alpha_val = rank_minus / rank_plus_safe
    
        
        # 3. Chuẩn hóa vị thế sang [-1, 1] qua rolling min-max
        window = 120
        r_min = self.feat.rolling_min(alpha_val, window)
        r_max = self.feat.rolling_max(alpha_val, window)
        scaled = (alpha_val - r_min) / (r_max - r_min + 1e-8)
        scaled = (scaled - 0.5) * 2.0
        
        # Reversal multiplier (Sharpe gốc âm, nhân -1 để thành dương)
        scaled = scaled * -1.0
        
        # Rời rạc hóa vị thế (Discretize)
        raw_pos = self.op.where(scaled > 0.5, 1.0, self.op.where(scaled < -0.5, -1.0, 0.0))
        # Giảm kích thước vị thế xuống 0.1 để quản trị Drawdown dưới 20%
        raw_pos = raw_pos * 0.1
        
        # Theo dõi giá vào lệnh (Entry price tracking)
        pos_changed = raw_pos != self.op.shift(raw_pos, 1)
        entry_price = self.op.fillna(close.where(pos_changed).ffill(), 0.0)
        
        # Logic Stop Loss động (15 điểm)
        sl_points = 15.0
        is_long = raw_pos > 0
        is_short = raw_pos < 0
        
        sl_long = is_long & (close <= (entry_price - sl_points))
        sl_short = is_short & (close >= (entry_price + sl_points))
        sl_triggered = sl_long | sl_short
        
        positions = self.op.where(sl_triggered, 0.0, raw_pos)
        positions = self.op.fillna(positions, 0.0)
        
        # 4. Set positions (EXIT trước, ENTRY sau)
        flat_mask = positions == 0.0
        long_mask = positions == 0.1
        short_mask = positions == -0.1
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position=0.1)
        self.set_positions(short_mask, position=-0.1)
