from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.bb_period = int(self.bb_period if 'bb_period' in self.__dict__ else 43)
        self.bb_std = float(self.bb_std if 'bb_std' in self.__dict__ else 1.6910312566480805)
        
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
