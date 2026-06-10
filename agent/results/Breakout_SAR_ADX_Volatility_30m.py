from backtest.strategy import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Khai báo các tham số tối ưu hóa
        sar_accel = float(getattr(self, 'sar_accel', 0.02))
        sar_max = float(getattr(self, 'sar_max', 0.2))
        adx_period = int(getattr(self, 'adx_period', 14))
        adx_threshold = float(getattr(self, 'adx_threshold', 25.0))
        atr_period = int(getattr(self, 'atr_period', 14))
        vol_factor = float(getattr(self, 'vol_factor', 1.0))
        sl_mult = float(getattr(self, 'sl_mult', 2.0))
        tp_mult = float(getattr(self, 'tp_mult', 3.0))

        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low

        # 2. Tính indicators
        sar = self.feat.sar(high, low, acceleration=sar_accel, maximum=sar_max)
        adx = self.feat.adx(high, low, close, timeperiod=adx_period)
        trange = self.feat.trange(high, low, close)
        atr = self.feat.atr(high, low, close, timeperiod=atr_period)

        # 3. Điều kiện Entry
        # Breakout SAR
        sar_cross_up = (close > sar) & (close.shift(1) <= sar.shift(1))
        sar_cross_down = (close < sar) & (close.shift(1) >= sar.shift(1))
        
        # Volatility filter
        vol_confirm = trange > (atr * vol_factor)
        
        long_setup = sar_cross_up & (adx > adx_threshold) & vol_confirm
        short_setup = sar_cross_down & (adx > adx_threshold) & vol_confirm

        # 4. Theo dõi giá vào lệnh để tính TP/SL
        long_entry_prices = close.where(long_setup).ffill()
        short_entry_prices = close.where(short_setup).ffill()

        # 5. Điều kiện Exit
        # Thoát khi: TP/SL, hoặc giá cắt ngược SAR
        tp_long = close >= (long_entry_prices + tp_mult * atr)
        sl_long = close <= (long_entry_prices - sl_mult * atr)
        early_exit_long = close < sar
        
        tp_short = close <= (short_entry_prices - tp_mult * atr)
        sl_short = close >= (short_entry_prices + sl_mult * atr)
        early_exit_short = close > sar

        exit_setup = tp_long | sl_long | early_exit_long | tp_short | sl_short | early_exit_short

        # 6. Set positions (Exit trước, Entry sau)
        self.set_positions(exit_setup, position=0)
        self.set_positions(long_setup, position=1)
        self.set_positions(short_setup, position=-1)