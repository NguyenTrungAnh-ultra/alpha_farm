from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        angle_period = int(getattr(self, 'angle_period', 14))
        angle_threshold = float(getattr(self, 'angle_threshold', 20.0))
        aroon_period = int(getattr(self, 'aroon_period', 14))
        aroon_threshold = float(getattr(self, 'aroon_threshold', 50))
        atr_period = int(getattr(self, 'atr_period', 14))
        sl_mult = float(getattr(self, 'sl_mult', 2.0))
        tp_mult = float(getattr(self, 'tp_mult', 4.0))

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 2. Tính indicators
        angle = self.feat.linearreg_angle(close, timeperiod=angle_period)
        aroonosc = self.feat.aroonosc(high, low, timeperiod=aroon_period)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)

        # 3. Tạo điều kiện entry
        long_setup = (angle > angle_threshold) & (aroonosc > aroon_threshold)
        short_setup = (angle < -angle_threshold) & (aroonosc < -aroon_threshold)

        # 4. Theo dõi giá vào lệnh để tính TP/SL
        long_entry_prices = close.where(long_setup).ffill()
        short_entry_prices = close.where(short_setup).ffill()

        # 5. Điều kiện exit
        # Exit Long: TP, SL, hoặc AROONOSC cắt xuống dưới 0
        exit_long_tp = close >= (long_entry_prices + tp_mult * atr)
        exit_long_sl = close <= (long_entry_prices - sl_mult * atr)
        exit_long_early = (aroonosc < 0) & (aroonosc.shift(1) >= 0)
        
        # Exit Short: TP, SL, hoặc AROONOSC cắt lên trên 0
        exit_short_tp = close <= (short_entry_prices - tp_mult * atr)
        exit_short_sl = close >= (short_entry_prices + sl_mult * atr)
        exit_short_early = (aroonosc > 0) & (aroonosc.shift(1) <= 0)

        # Tổng hợp tín hiệu thoát
        exit_setup = exit_long_tp | exit_long_sl | exit_long_early | exit_short_tp | exit_short_sl | exit_short_early

        # 6. Set positions (EXIT trước, ENTRY sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)