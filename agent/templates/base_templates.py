def generate_ema_crossover_code(params: dict) -> str:
    return f"""from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.fast_period = int(self.fast_period if 'fast_period' in self.__dict__ else {int(params['fast_period'])})
        self.slow_period = int(self.slow_period if 'slow_period' in self.__dict__ else {int(params['slow_period'])})
        
        fast_period = self.fast_period
        slow_period = self.slow_period
        
        # 2. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        
        # 3. Indicators
        ema_fast = self.feat.ema(close, timeperiod=fast_period)
        ema_slow = self.feat.ema(close, timeperiod=slow_period)
        
        # 4. Entry logic
        long_setup = (close > ema_slow) & (ema_fast > ema_slow)
        short_setup = (close < ema_slow) & (ema_fast < ema_slow)
        
        # 5. Exit logic
        exit_long = close < ema_fast
        exit_short = close > ema_fast
        exit_setup = exit_long | exit_short
        
        # 6. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
"""

def generate_rsi_mean_reversion_code(params: dict) -> str:
    return f"""from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.rsi_period = int(self.rsi_period if 'rsi_period' in self.__dict__ else {int(params['rsi_period'])})
        self.rsi_lower = float(self.rsi_lower if 'rsi_lower' in self.__dict__ else {float(params['rsi_lower'])})
        self.rsi_upper = float(self.rsi_upper if 'rsi_upper' in self.__dict__ else {float(params['rsi_upper'])})
        self.ema_filter_period = int(self.ema_filter_period if 'ema_filter_period' in self.__dict__ else {int(params['ema_filter_period'])})
        
        rsi_period = self.rsi_period
        rsi_lower = self.rsi_lower
        rsi_upper = self.rsi_upper
        ema_filter_period = self.ema_filter_period
        
        # 2. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        
        # 3. Indicators
        rsi = self.feat.rsi(close, timeperiod=rsi_period)
        ema_filter = self.feat.ema(close, timeperiod=ema_filter_period)
        
        # 4. Entry logic
        long_setup = (close > ema_filter) & (rsi < rsi_lower)
        short_setup = (close < ema_filter) & (rsi > rsi_upper)
        
        # 5. Exit logic
        exit_long = (rsi > 50.0) | (close < ema_filter)
        exit_short = (rsi < 50.0) | (close > ema_filter)
        exit_setup = exit_long | exit_short
        
        # 6. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
"""

def generate_bollinger_breakout_code(params: dict) -> str:
    return f"""from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else {int(params['bb_period'])})
        self.bb_std = float(self.bb_std if 'bb_std' in self.__dict__ else {float(params['bb_std'])})
        
        bb_period = self.bb_period
        bb_std = self.bb_std
        
        # 2. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        
        # 3. Indicators
        bb = self.feat.bbands(close, timeperiod=bb_period, nbdevup=bb_std, nbdevdn=bb_std)
        upper_band = bb[0]
        middle_band = bb[1]
        lower_band = bb[2]
        
        # 4. Entry logic
        long_setup = self.op.crossed_above(close, upper_band)
        short_setup = self.op.crossed_below(close, lower_band)
        
        # 5. Exit logic
        exit_long = close < middle_band
        exit_short = close > middle_band
        exit_setup = exit_long | exit_short
        
        # 6. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
"""

TEMPLATE_REGISTRY = {
    "EmaCrossoverTemplate": {
        "description": "Trend-following strategy using fast and slow EMA crossovers.",
        "params": {
            "fast_period": {"type": "int", "low": 5, "high": 30, "default": 12},
            "slow_period": {"type": "int", "low": 35, "high": 120, "default": 50}
        },
        "generate_code": generate_ema_crossover_code
    },
    "RsiMeanReversionTemplate": {
        "description": "Mean reversion strategy trading RSI overbought/oversold levels in the direction of a long-term trend filter.",
        "params": {
            "rsi_period": {"type": "int", "low": 5, "high": 30, "default": 14},
            "rsi_lower": {"type": "float", "low": 10.0, "high": 40.0, "default": 30.0},
            "rsi_upper": {"type": "float", "low": 60.0, "high": 90.0, "default": 70.0},
            "ema_filter_period": {"type": "int", "low": 20, "high": 200, "default": 100}
        },
        "generate_code": generate_rsi_mean_reversion_code
    },
    "BollingerBreakoutTemplate": {
        "description": "Breakout strategy entering positions when close price breaks outer Bollinger Bands and exiting at middle band.",
        "params": {
            "bb_period": {"type": "int", "low": 10, "high": 50, "default": 20},
            "bb_std": {"type": "float", "low": 1.0, "high": 3.0, "default": 2.0}
        },
        "generate_code": generate_bollinger_breakout_code
    }
}
