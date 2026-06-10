from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        t3_period = int(getattr(self, 't3_period', 46))
        ultosc_short = int(getattr(self, 'ultosc_short', 12))
        ultosc_medium = int(getattr(self, 'ultosc_medium', 14))
        adosc_fast = int(getattr(self, 'adosc_fast', 10))
        adosc_slow = int(getattr(self, 'adosc_slow', 24))

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume

        # 2. Tính toán indicators
        t3 = self.feat.t3(close, timeperiod=t3_period)
        ultosc = self.feat.ultosc(high, low, close, timeperiod1=ultosc_short, timeperiod2=ultosc_medium, timeperiod3=28)
        adosc = self.feat.adosc(high, low, close, volume, fastperiod=adosc_fast, slowperiod=adosc_slow)
        
        # 3. Logic Exit (Thoát trước)
        # Giá cắt ngược T3
        exit_t3 = ((close < t3) & (close.shift(1) >= t3.shift(1))) | ((close > t3) & (close.shift(1) <= t3.shift(1)))
        # UltOsc quá mua/quá bán
        exit_ult = (ultosc > 70) | (ultosc < 30)
        
        exit_setup = exit_t3 | exit_ult

        # 4. Logic Entry
        # UltOsc cắt 50
        ultosc_cross_up = (ultosc > 50) & (ultosc.shift(1) <= 50)
        ultosc_cross_down = (ultosc < 50) & (ultosc.shift(1) >= 50)
        
        long_setup = (close > t3) & ultosc_cross_up & (adosc > 0)
        short_setup = (close < t3) & ultosc_cross_down & (adosc < 0)

        # 5. Set positions (EXIT trước, ENTRY sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)