from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # Parameters
        self.orb_window = 12
        self.atr_period = 14
        self.sma_period = 20
        self.atr_multiplier = 1.2
        self.position_close_after_n_candles = 9
        self.position_open_ranges = ["02:00-07:29"]
        self.position_close_ranges = ["07:30-07:45"]
        
        # Data
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        
        # 1. Donchian Channels (Highest High / Lowest Low)
        highest_high = self.feat.rolling_max(high, self.orb_window)
        lowest_low = self.feat.rolling_min(low, self.orb_window)
        
        prev_highest = self.op.shift(highest_high, 1)
        prev_lowest = self.op.shift(lowest_low, 1)
        
        # 2. ATR & Momentum Filter
        atr = self.feat.atr(high, low, close, self.atr_period)
        candle_range = high - low
        
        # 3. Trailing Stop (SMA)
        sma = self.feat.sma(close, self.sma_period)
        
        # 4. Entry Logic
        # Breakout above highest high with strong candle
        long_setup = (close > prev_highest) & (candle_range > self.atr_multiplier * self.op.shift(atr, 1))
        
        # Breakout below lowest low with strong candle
        short_setup = (close < prev_lowest) & (candle_range > self.atr_multiplier * self.op.shift(atr, 1))
        
        # 5. Exit Logic (Trailing Stop)
        # Exit long if price crosses below SMA
        exit_long = close < sma
        # Exit short if price crosses above SMA
        exit_short = close > sma
        flat_zone = exit_long | exit_short
        
        # 6. Execute Orders
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
