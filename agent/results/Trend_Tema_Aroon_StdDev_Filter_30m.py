from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        tema_period = int(getattr(self, 'tema_period', 30))
        aroon_period = int(getattr(self, 'aroon_period', 20))
        stddev_period = int(getattr(self, 'stddev_period', 20))

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 2. Indicators
        tema = self.feat.tema(close, timeperiod=tema_period)
        aroon_down, aroon_up = self.feat.aroon(high, low, timeperiod=aroon_period)
        
        # Volatility filter
        stddev = self.feat.stddev(close, timeperiod=stddev_period)
        stddev_ma = self.feat.sma(stddev, timeperiod=stddev_period)
        vol_filter = stddev > stddev_ma

        # 3. Logic điều kiện
        long_setup = (aroon_up > 70) & (aroon_down < 30) & (close > tema) & vol_filter
        short_setup = (aroon_down > 70) & (aroon_up < 30) & (close < tema) & vol_filter
        
        # 4. Exit logic
        # (1) Aroon cắt xuống dưới 50, (2) Giá cắt ngược TEMA
        exit_long = (aroon_up < 50) | (close < tema)
        exit_short = (aroon_down < 50) | (close > tema)
        exit_setup = exit_long | exit_short

        # 5. Set positions (EXIT trước, ENTRY sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)