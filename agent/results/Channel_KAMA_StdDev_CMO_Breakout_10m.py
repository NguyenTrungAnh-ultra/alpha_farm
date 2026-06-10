from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        kama_period = int(getattr(self, 'kama_period', 20))
        std_period = int(getattr(self, 'std_period', 20))
        std_mult = float(getattr(self, 'std_mult', 2.0))
        cmo_period = int(getattr(self, 'cmo_period', 14))
        cmo_threshold = float(getattr(self, 'cmo_threshold', 20.0))
        sl_points = float(getattr(self, 'sl_points', 7.0))

        # 2. Lấy dữ liệu giá
        close = self.data.pv_close

        # 3. Tính indicators (vectorized, qua self.feat)
        kama = self.feat.kama(close, timeperiod=kama_period)
        stddev = self.feat.stddev(close, timeperiod=std_period)
        cmo = self.feat.cmo(close, timeperiod=cmo_period)

        # Tính toán biên trên và biên dưới của kênh
        upper_band = kama + (std_mult * stddev)
        lower_band = kama - (std_mult * stddev)

        # 4. Tạo điều kiện entry/exit
        long_setup = (close > upper_band) & (cmo > cmo_threshold)
        short_setup = (close < lower_band) & (cmo < -cmo_threshold)

        exit_long = close < kama
        exit_short = close > kama
        exit_setup = exit_long | exit_short

        # 5. Set positions (EXIT trước, ENTRY sau để override)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)