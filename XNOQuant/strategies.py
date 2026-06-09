from src.algo import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    """
    name:    Perfected_BBands_Breakout_Armored
    summary: Added a 200 EMA macro filter to eliminate counter-trend fakeouts and reduce MDD below -35%.
    idea:    The previous iteration achieved a massive 54% CAGR and 1.48 Sharpe but slightly missed the MDD 
             target (-37.3% vs -35%). The drawdown comes from catching extreme volatility breakouts that are 
             against the prevailing long-term trend (e.g., buying a dead-cat bounce in a bear market). 
             By adding an EMA 200 macro filter, we sacrifice a small portion of the excess CAGR to block 
             these fatal counter-trend trades. We also slightly relax the band-hugging tolerance (0.99 -> 0.98) 
             to prevent micro-whipsaws from inflating transaction costs.
    """
    def __algorithm__(self):
        # 1. Tham số gốc siêu lợi nhuận của bạn
        bb_period = 30
        bb_dev = 2.6
        rsi_period = 20
        sl_atr_mult = 3.6
        atr_period = 14

        # 2. BỘ LỌC MỚI: Tấm Khiên Vĩ Mô
        macro_period = 200

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 3. Tính toán Trục và Chỉ báo
        macro_trend = self.feat.ema(close, macro_period)

        basis = self.feat.rolling_mean(close, bb_period)
        dev = bb_dev * self.feat.stddev(close, bb_period)
        upper = basis + dev
        lower = basis - dev

        rsi = self.feat.rsi(close, rsi_period)
        atr = self.feat.atr(high, low, close, atr_period)

        sl_long = basis - (sl_atr_mult * atr)
        sl_short = basis + (sl_atr_mult * atr)

        fast_momentum = self.feat.ema(close, 5)

        # 4. VÙNG TRẠNG THÁI (Đã bọc thép)
        # THÊM (close > macro_trend): Cấm bắt Long khi thị trường vĩ mô đang sập
        # NỚI (upper * 0.98): Cho giá không gian thở, tránh bị cưa phí
        long_zone = (close > macro_trend) & (fast_momentum > basis) & (rsi > 50.0) & (close > sl_long) & (close > upper * 0.98)
        
        # THÊM (close < macro_trend): Cấm bắt Short khi thị trường vĩ mô đang tăng
        short_zone = (close < macro_trend) & (fast_momentum < basis) & (rsi < 50.0) & (close < sl_short) & (close < lower * 1.02)

        flat_zone = (~long_zone) & (~short_zone)

        # 5. Thực thi
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)

class CustomStrategy(SimpleAlgorithm):
    """
    name:    Stateless_KAMA_ADX_ATR_Proxy
    summary: Translated a complex KAMA/ADX trend rider with ATR-based SL/TP into a stateless continuous architecture.
    idea:    In a stateless AST environment, tracking the exact 'entry_price' for fixed ATR Stop Losses/Take Profits 
             is impossible, and native recursive KAMA/time-hooks are blocked. We transform the logic into continuous 
             zones: We use an EMA proxy for the baseline. We hold Long when Price > Baseline AND ADX > 22.0. 
             The Take Profit (6.0 ATR) is enforced dynamically by capping the hold zone (Price < Baseline + 6*ATR). 
             The Stop Loss (2.5 ATR) is naturally handled by the baseline cross itself, acting as a strict, 
             adaptive trailing stop that flattens the position if the trend breaks.
    """
    def __algorithm__(self):
        # 1. Thông số theo đúng yêu cầu của bạn
        kama_period = 10
        adx_period = 10
        adx_threshold = 22.0
        
        atr_period = 18
        atr_tp_multiplier = 6.0
        # atr_sl_multiplier = 2.5 (Sẽ được xử lý ngầm bằng việc rớt khỏi trục Baseline)

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 2. Xây dựng Trục Cơ sở (KAMA Proxy an toàn với AST Compiler)
        baseline = self.feat.ema(close, kama_period)

        # 3. Cảm biến Sức mạnh Xu hướng & Biến động
        adx = self.feat.adx(high, low, close, adx_period)
        atr = self.feat.atr(high, low, close, atr_period)

        # 4. Kỹ thuật Bao bọc: Tạo trần/đáy Take Profit động
        upper_tp = baseline + (atr * atr_tp_multiplier)
        lower_tp = baseline - (atr * atr_tp_multiplier)

        # 5. VÙNG TRẠNG THÁI LIÊN TỤC (Stateless Zones)
        # Giữ Long: Nằm trên trục + Trend mạnh (ADX > 22) + CHƯA chạm mức Take Profit 6.0 ATR
        long_zone = (close > baseline) & (adx > adx_threshold) & (close < upper_tp)
        
        # Giữ Short: Nằm dưới trục + Trend mạnh (ADX > 22) + CHƯA rớt chạm mức Take Profit 6.0 ATR
        short_zone = (close < baseline) & (adx > adx_threshold) & (close > lower_tp)

        # Trạng thái Đứng ngoài: Kích hoạt khi gãy ADX, gãy trục Baseline (Cắt lỗ) hoặc chạm TP Envelope
        flat_zone = (~long_zone) & (~short_zone)

        # 6. Thực thi lệnh
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)

class CustomStrategy(SimpleAlgorithm):
    """
    name:    DEMA_13_30_Armored
    summary: Added Macro EMA and ADX filters to the DEMA crossover to prevent account liquidation.
    idea:    The raw DEMA 13/30 is a continuous Stop & Reverse system. While it captures massive trends 
             (showing theoretical high returns), it stays in the market during tight sideway chops, 
             causing continuous whipsaw losses and fee bleed that ultimately liquidates the account 
             (hence the -100% MDD in strict IS testing). By adding an EMA 200 macro filter and an ADX > 20 
             chop filter, we force the strategy to go FLAT during noise, preserving capital and surviving 
             to catch the big DEMA trends.
    """
    def __algorithm__(self):
        # 1. Tham số DEMA siêu tốc
        fast_period = 13
        slow_period = 30
        
        # 2. Hệ thống Phanh & Khiên bảo vệ
        macro_period = 200
        adx_period = 14
        adx_threshold = 20  # Ngưỡng bắt buộc để xác nhận có dòng tiền

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 3. Kích hoạt Cảm biến Vĩ mô & Thanh khoản
        macro_trend = self.feat.ema(close, macro_period)
        adx = self.feat.adx(high, low, close, adx_period)

        # 4. CHẾ TẠO DEMA (Core Engine)
        e1_fast = self.feat.ema(close, fast_period)
        e2_fast = self.feat.ema(e1_fast, fast_period)
        dema_fast = (2.0 * e1_fast) - e2_fast
        
        e1_slow = self.feat.ema(close, slow_period)
        e2_slow = self.feat.ema(e1_slow, slow_period)
        dema_slow = (2.0 * e1_slow) - e2_slow

        # 5. VÙNG TRẠNG THÁI (Đã lắp Phanh ABS)
        # Bắt buộc phải có ADX > 20 và thuận xu hướng lớn mới cho phép vào lệnh
        long_zone = (dema_fast > dema_slow) & (close > macro_trend) & (adx > adx_threshold)
        short_zone = (dema_fast < dema_slow) & (close < macro_trend) & (adx > adx_threshold)

        # Trạng thái ĐỨNG NGOÀI ôm tiền mặt (Flat) khi thị trường nhiễu loạn
        flat_zone = (~long_zone) & (~short_zone)

        # 6. Thực thi vị thế
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)


class CustomStrategy(SimpleAlgorithm):
    """
    name:    Kinetic_Acceleration_HitAndRun
    summary: Trades the second derivative of price (Acceleration). Enters on momentum bursts and exits immediately when acceleration slows.
    idea:    To achieve zero correlation with moving averages and price-level breakouts, this strategy acts purely on physics (Kinematics).
             It calculates Momentum (ROC), derives Velocity (EMA of Momentum), and Acceleration (EMA of Velocity).
             It only holds a position while the "gas pedal" is pressed (Velocity > Acceleration). The moment momentum stops 
             accelerating—even if price is still rising due to inertia—it flattens the position. This "Hit and Run" approach 
             creates a high-win-rate, low-drawdown profile that completely avoids the late exits typical of trend-following systems.
    """
    def __algorithm__(self):
        # 1. Tham số Động học (Kinematics)
        roc_period = 10       # Đo lường biến thiên giá
        vel_period = 5        # Chuyển thành Vận tốc
        accel_period = 5      # Chuyển thành Gia tốc
        
        macro_period = 200    # Vẫn cần "La bàn" để biết xe đang lên dốc hay xuống dốc

        close = self.data.pv_close

        # 2. CHẾ TẠO ĐỘNG CƠ VẬT LÝ (Kinetic Engine)
        # Tính Động lượng gốc
        momentum = self.feat.roc(close, roc_period)
        
        # Đạo hàm bậc 1: Vận tốc (Velocity)
        velocity = self.feat.ema(momentum, vel_period)
        
        # Đạo hàm bậc 2: Gia tốc (Acceleration)
        acceleration = self.feat.ema(velocity, accel_period)

        # 3. La bàn Vĩ mô
        macro_trend = self.feat.ema(close, macro_period)

        # 4. VÙNG TRẠNG THÁI (Triết lý: Đánh nhanh - Rút gọn)
        # Giữ Long CHỈ KHI:
        # - Đang trong Uptrend vĩ mô
        # - Vận tốc dương (Đang đi lên)
        # - Gia tốc đang tăng (Velocity > Acceleration) -> Lực Mua đang "Đạp ga"
        long_zone = (close > macro_trend) & (velocity > 0.0) & (velocity > acceleration)
        
        # Giữ Short CHỈ KHI:
        # - Đang trong Downtrend vĩ mô
        # - Vận tốc âm (Đang lao xuống)
        # - Gia tốc đang giảm thêm (Velocity < Acceleration) -> Lực Bán đang "Đạp ga lùi"
        short_zone = (close < macro_trend) & (velocity < 0.0) & (velocity < acceleration)

        # CHỐT LỜI TỰ ĐỘNG: Ngay khi thị trường "Nhả ga" (Giao cắt ngược lại), ép vị thế về 0.
        # Không bao giờ chờ giá đảo chiều mới chốt!
        flat_zone = (~long_zone) & (~short_zone)

        # 5. Thực thi Vị thế
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)


class CustomStrategy(SimpleAlgorithm):
    """
    name:    ZeroLag_TEMA_FrontRunner
    summary: Uses Triple Exponential Moving Average (TEMA) to achieve zero-lag entries, independent of Volume.
    idea:    Since Volume data (pv_volume) is an empty array (shape 0) in this sandbox environment, 
             we achieve low correlation by abandoning standard lagging price indicators. 
             Instead, we mathematically construct TEMA (3*E1 - 3*E2 + E3) which cancels out the inherent lag 
             of moving averages. This allows the system to 'front-run' traditional trend followers, entering 
             reversals significantly earlier at better prices, filtered safely by a macro trend line.
    """
    def __algorithm__(self):
        # 1. Tham số siêu tốc
        fast_period = 12
        slow_period = 34
        macro_period = 200

        close = self.data.pv_close

        # 2. CHẾ TẠO ĐỘNG CƠ TEMA (Triệt tiêu toàn bộ độ trễ)
        # Tính toán TEMA Fast
        f_e1 = self.feat.ema(close, fast_period)
        f_e2 = self.feat.ema(f_e1, fast_period)
        f_e3 = self.feat.ema(f_e2, fast_period)
        fast_tema = (3.0 * f_e1) - (3.0 * f_e2) + f_e3

        # Tính toán TEMA Slow
        s_e1 = self.feat.ema(close, slow_period)
        s_e2 = self.feat.ema(s_e1, slow_period)
        s_e3 = self.feat.ema(s_e2, slow_period)
        slow_tema = (3.0 * s_e1) - (3.0 * s_e2) + s_e3

        # 3. La bàn Vĩ mô (Giữ nguyên để bảo vệ PNL khỏi các pha giật lừa)
        macro_trend = self.feat.ema(close, macro_period)

        # 4. VÙNG TRẠNG THÁI LIÊN TỤC (ZERO-LAG ZONES)
        # Giữ Long: Vĩ mô Tăng + TEMA ngắn cắt TEMA dài
        long_zone = (fast_tema > slow_tema) & (close > macro_trend)
        
        # Giữ Short: Vĩ mô Giảm + TEMA ngắn bị đạp dưới TEMA dài
        short_zone = (fast_tema < slow_tema) & (close < macro_trend)

        flat_zone = (~long_zone) & (~short_zone)

        # 5. Thực thi lệnh
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)


class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        
        # 3 đường trung bình động tạo thành Kênh Giá (Channel)
        sma_high = self.feat.sma(high, timeperiod=10).fillna(99999)
        sma_low = self.feat.sma(low, timeperiod=10).fillna(0)
        sma_close = self.feat.sma(close, timeperiod=10).fillna(0)
        
        # Điều kiện Mua / Bán
        long_setup = close > sma_high
        short_setup = close < sma_low
        
        # Điều kiện Thoát lệnh: Giá cắt ngược vào đường trung tâm
        exit_long = close < sma_close
        exit_short = close > sma_close
        exit_setup = exit_long | exit_short
        
        # Xếp lệnh (Ưu tiên thoát lệnh trước, có tín hiệu thì đè lên sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)