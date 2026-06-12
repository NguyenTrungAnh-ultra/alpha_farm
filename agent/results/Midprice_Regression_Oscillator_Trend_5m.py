from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.anchor_period = int(getattr(self, 'anchor_period', 32))
        self.channel_mult = float(getattr(self, 'channel_mult', 1.2))
        self.adxr_min = float(getattr(self, 'adxr_min', 17.0))
        self.exit_period = int(getattr(self, 'exit_period', 16))
        self.exit_mult = float(getattr(self, 'exit_mult', 3.4))

        # 2. Local variables for parameters
        anchor_period = self.anchor_period
        channel_mult = self.channel_mult
        adxr_min = self.adxr_min
        exit_period = self.exit_period
        exit_mult = self.exit_mult

        # 3. Inputs
        open = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        Mid_Anchor = self.feat.midprice(high, low, timeperiod=anchor_period)
        StdDev = self.feat.stddev(close, timeperiod=anchor_period)
        Upper_Channel = Mid_Anchor + (channel_mult * StdDev)
        Lower_Channel = Mid_Anchor - (channel_mult * StdDev)
        ADXR = self.feat.adxr(high, low, close, timeperiod=14)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Rolling_Max = self.feat.max(high, timeperiod=exit_period)
        Rolling_Min = self.feat.min(low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > Upper_Channel) & (ADXR > adxr_min)
        short_setup = (close < Lower_Channel) & (ADXR > adxr_min)

        # 6. Exit logic
        exit_long = (close < Mid_Anchor) | (close < Rolling_Max - (exit_mult * ATR))
        exit_short = (close > Mid_Anchor) | (close > Rolling_Min + (exit_mult * ATR))
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
