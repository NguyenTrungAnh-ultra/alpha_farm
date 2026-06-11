from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        channel_period = int(getattr(self, 'channel_period', 5))
        roc_period = int(getattr(self, 'roc_period', 20))
        atr_filter = float(getattr(self, 'atr_filter', 2.5))

        # 2. Lấy dữ liệu giá
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        
        # 3. TÍNH TOÁN KÊNH GIÁ (PRICE CHANNEL)
        # Sử dụng minmax để tìm đỉnh/đáy trong channel_period
        lowest_low, _ = self.feat.minmax(low, timeperiod=channel_period)
        _, highest_high = self.feat.minmax(high, timeperiod=channel_period)
        
        # Shift 1 để lấy kênh giá của N nến trước đó, tránh bias
        session_high_prev = highest_high.shift(1)
        session_low_prev = lowest_low.shift(1)
        
        # 4. TÍNH TOÁN CÁC CHỈ BÁO KHÁC
        roc = self.feat.roc(close, timeperiod=roc_period)
        atr = self.feat.atr(high, low, close, timeperiod=14) 
        
        # Dùng SMA thay cho .rolling().mean() để an toàn qua bộ lọc XNO Quant
        sma_roc_period = self.feat.sma(close, timeperiod=roc_period)
        
        # 5. ĐIỀU KIỆN VÀO LỆNH (ENTRY SETUP)
        not_extended = abs(close - sma_roc_period) < (atr_filter * atr)
        
        long_setup = (close > session_high_prev) & (roc > 0) & not_extended
        short_setup = (close < session_low_prev) & (roc < 0) & not_extended
        
        # 6. ĐIỀU KIỆN THOÁT LỆNH (EXIT SETUP)
        exit_roc = (roc > 5.0) | (roc < -5.0)
        exit_reentry = (close < session_high_prev) & (close > session_low_prev)
        exit_setup = exit_roc | exit_reentry
        
        # 7. KÍCH HOẠT LỆNH
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)