from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        bbands_period = int(getattr(self, 'bbands_period', 45))
        bbands_stddev = float(getattr(self, 'bbands_stddev', 1.5))
        dema_period = int(getattr(self, 'dema_period', 45))
        atr_period = int(getattr(self, 'atr_period', 24))
        sl_mult = float(getattr(self, 'sl_mult', 2.0))
        tp_points = float(getattr(self, 'tp_points', 20))

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 2. Tính các chỉ báo kỹ thuật
        upper, middle, lower = self.feat.bbands(close, timeperiod=bbands_period, nbdevup=bbands_stddev, nbdevdn=bbands_stddev)
        dema = self.feat.dema(close, timeperiod=dema_period)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)

        # Logic Squeeze: Khoảng cách giữa các dải đang thu hẹp (dùng rolling_mean thay cho .rolling().mean())
        bandwidth = (upper - lower) / middle
        is_squeeze = bandwidth < self.feat.rolling_mean(bandwidth, 20)

        # 3. Điều kiện Entry
        # Entry Long: Breakout upper, giá > DEMA, đang trong trạng thái squeeze
        long_setup = (close > upper) & (close > dema) & is_squeeze
        
        # Entry Short: Breakout lower, giá < DEMA, đang trong trạng thái squeeze
        short_setup = (close < lower) & (close < dema) & is_squeeze

        # 4. Theo dõi giá vào lệnh để tính TP/SL
        long_entry_prices = close.where(long_setup).ffill()
        short_entry_prices = close.where(short_setup).ffill()

        # 5. Điều kiện Exit
        # Thoát lệnh: chạm TP, SL hoặc giá cắt ngược qua Middle Band
        tp_long = close >= (long_entry_prices + tp_points)
        sl_long = close <= (long_entry_prices - sl_mult * atr)
        early_exit_long = close < middle
        
        tp_short = close <= (short_entry_prices - tp_points)
        sl_short = close >= (short_entry_prices + sl_mult * atr)
        early_exit_short = close > middle

        exit_setup = tp_long | sl_long | early_exit_long | tp_short | sl_short | early_exit_short

        # 6. Đặt lệnh (Exit trước, Entry sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)