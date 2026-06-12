from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        self.channel_period = 30
        self.obv_sma_period = 20
        self.exit_sma_period = 10
        
        # 1. Lấy dữ liệu giá và khối lượng
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume

        # 2. Tính indicators
        # Kênh Donchian
        highest_high = self.feat.max(high, timeperiod=self.channel_period)
        lowest_low = self.feat.min(low, timeperiod=self.channel_period)
        
        # Dịch chuyển 1 nến để lấy giá trị của nến trước đó
        prev_highest_high = self.op.shift(highest_high, 1)
        prev_lowest_low = self.op.shift(lowest_low, 1)

        # OBV và SMA của OBV
        obv = self.feat.obv(close, volume)
        obv_sma = self.feat.sma(obv, timeperiod=self.obv_sma_period)

        # SMA ngắn hạn dùng cho trailing stop / exit
        exit_sma = self.feat.sma(close, timeperiod=self.exit_sma_period)

        # 3. Tạo điều kiện entry/exit
        long_setup = (close > prev_highest_high) & (obv > obv_sma)
        short_setup = (close < prev_lowest_low) & (obv < obv_sma)

        exit_long = close < exit_sma
        exit_short = close > exit_sma
        exit_setup = exit_long | exit_short

        # 4. Set positions (EXIT trước, ENTRY sau để override)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)