from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        self.period_aroon = 50
        self.period_midprice = 50
        self.threshold_aroon = 70
        self.atr_exit_multiplier = 2.5
        
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 1. Tính indicators
        aroon_osc = self.feat.aroonosc(high, low, timeperiod=self.period_aroon)
        midprice = self.feat.midprice(high, low, timeperiod=self.period_midprice)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        
        # 2. Logic Entry
        long_setup = (aroon_osc > self.threshold_aroon) & (close > midprice)
        short_setup = (aroon_osc < -self.threshold_aroon) & (close < midprice)
        
        # 3. Logic Exit
        # Thoát khi AroonOsc cắt 0 hoặc giá biến động quá mạnh (quá nhiệt) so với ATR
        # Sử dụng diff để xác định điểm cắt ngang mức 0
        exit_aroon = ((aroon_osc < 0) & (self.op.shift(aroon_osc, 1) >= 0)) | \
                     ((aroon_osc > 0) & (self.op.shift(aroon_osc, 1) <= 0))
        
        # Logic quá nhiệt (đơn giản hóa bằng độ lệch so với trung bình)
        diff = close - midprice
        abs_diff = self.op.where(diff > 0, diff, -diff)
        exit_overheat = (abs_diff > (self.atr_exit_multiplier * atr))
        
        exit_setup = exit_aroon | exit_overheat
        
        # 4. Set positions (EXIT trước, ENTRY sau)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)