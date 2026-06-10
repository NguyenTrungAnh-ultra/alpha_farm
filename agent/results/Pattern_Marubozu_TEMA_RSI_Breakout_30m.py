from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        tema_period = int(getattr(self, 'tema_period', 26))
        rsi_period = int(getattr(self, 'rsi_period', 30))
        rsi_upper_limit = float(getattr(self, 'rsi_upper_limit', 66.0))
        rsi_lower_limit = float(getattr(self, 'rsi_lower_limit', 39.0))

        # 2. Lấy dữ liệu giá
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close

        # 3. Tính toán indicators
        tema = self.feat.tema(close, timeperiod=tema_period)
        rsi = self.feat.rsi(close, timeperiod=rsi_period)

        # 4. Xác định nến Marubozu (Body chiếm ít nhất 95% biên độ High-Low)
        body = abs(close - open_)
        candle_range = high - low
        # Tránh lỗi chia cho 0
        candle_range = candle_range.where(candle_range > 0, 0.0001)
        
        is_marubozu = (body / candle_range) >= 0.95

        # 5. Tạo điều kiện entry/exit
        long_setup = is_marubozu & (close > open_) & (close > tema) & (rsi < rsi_upper_limit)
        short_setup = is_marubozu & (close < open_) & (close < tema) & (rsi > rsi_lower_limit)

        exit_long = (close < tema) | (rsi > 85)
        exit_short = (close > tema) | (rsi < 15)
        exit_setup = exit_long | exit_short

        # 6. Set positions (EXIT trước, ENTRY sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)