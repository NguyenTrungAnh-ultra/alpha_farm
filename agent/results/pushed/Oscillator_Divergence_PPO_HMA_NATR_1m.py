class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo tham số (Parameters)
        self.hma_period = 6
        self.ppo_fast = 7
        self.ppo_slow = 15
        self.natr_period = 13
        self.natr_threshold = 0.2

        # 2. Lấy dữ liệu giá
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # ---------------------------------------------------------
        # 3. TÍNH TOÁN CHỈ BÁO
        # ---------------------------------------------------------
        
        # --- Hull Moving Average (HMA) ---
        # Tự tính HMA bằng 2 đường WMA, cực kỳ thông minh và chuẩn xác!
        wma_half = self.feat.wma(close, timeperiod=int(self.hma_period / 2))
        wma_full = self.feat.wma(close, timeperiod=self.hma_period)
        
        # Thay thế np.sqrt bằng phép toán lũy thừa cơ bản của Python (x ** 0.5)
        hma_smooth_period = int(self.hma_period ** 0.5)
        hma = self.feat.wma(2 * wma_half - wma_full, timeperiod=hma_smooth_period)
        
        # --- PPO & NATR ---
        ppo = self.feat.ppo(close, fastperiod=self.ppo_fast, slowperiod=self.ppo_slow, matype=0)
        signal = self.feat.ema(ppo, timeperiod=9)
        natr = self.feat.natr(high, low, close, timeperiod=self.natr_period)

        # Lưu vết quá khứ để tìm giao cắt (Sửa lỗi AST: Phải dùng self.op.shift)
        ppo_prev = self.op.shift(ppo, 1)
        signal_prev = self.op.shift(signal, 1)
        close_prev = self.op.shift(close, 1)
        hma_prev = self.op.shift(hma, 1)

        # ---------------------------------------------------------
        # 4. ĐIỀU KIỆN VÀO LỆNH (ENTRY SETUP)
        # ---------------------------------------------------------
        # Long khi: Giá nằm DƯỚI HMA, PPO âm nhưng đang ngóc LÊN, và biến động đủ lớn
        long_setup = (close < hma) & (ppo < 0) & (ppo > ppo_prev) & (natr > self.natr_threshold)
        
        # Short khi: Giá nằm TRÊN HMA, PPO dương nhưng đang chúi XUỐNG, và biến động đủ lớn
        short_setup = (close > hma) & (ppo > 0) & (ppo < ppo_prev) & (natr > self.natr_threshold)

        # ---------------------------------------------------------
        # 5. ĐIỀU KIỆN THOÁT LỆNH (EXIT SETUP)
        # ---------------------------------------------------------
        # Thoát Long: PPO cắt XUỐNG Signal, HOẶC Giá chốt lời cắt LÊN HMA
        exit_long_ppo = (ppo < signal) & (ppo_prev >= signal_prev)
        exit_long_hma = (close >= hma) & (close_prev < hma_prev)
        exit_long = exit_long_ppo | exit_long_hma
        
        # Thoát Short: PPO cắt LÊN Signal, HOẶC Giá chốt lời cắt XUỐNG HMA
        exit_short_ppo = (ppo > signal) & (ppo_prev <= signal_prev)
        exit_short_hma = (close <= hma) & (close_prev > hma_prev)
        exit_short = exit_short_ppo | exit_short_hma

        # Tổng hợp tín hiệu thoát
        exit_setup = exit_long | exit_short

        # ---------------------------------------------------------
        # 6. KÍCH HOẠT LỆNH
        # ---------------------------------------------------------
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
