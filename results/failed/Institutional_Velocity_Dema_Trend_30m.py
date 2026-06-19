from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.dema_period = 45
        self.mom_period = 21
        self.mom_threshold = 3.0
        self.adxr_period = 30
        self.adxr_min = 20.0
        self.exit_period = 22

        # 2. Local variables for parameters
        dema_period = self.dema_period
        mom_period = self.mom_period
        mom_threshold = self.mom_threshold
        adxr_period = self.adxr_period
        adxr_min = self.adxr_min
        exit_period = self.exit_period

        # 3. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume

        # 4. Indicators
        dema = self.feat.dema(close, timeperiod=dema_period)
        mom = self.feat.mom(close, timeperiod=mom_period)
        adxr = self.feat.adxr(high, low, close, timeperiod=adxr_period)
        atr = self.feat.atr(high, low, close, timeperiod=14)
        midprice_exit = self.feat.midprice(high, low, timeperiod=exit_period)

        # 5. Entry logic
        long_setup = (close > dema) & (mom > mom_threshold) & (adxr > adxr_min)
        short_setup = (close < dema) & (mom < -mom_threshold) & (adxr > adxr_min)

        # 6. Exit logic
        exit_long = (close < midprice_exit - 0.5 * atr) | (mom < 0.0)
        exit_short = (close > midprice_exit + 0.5 * atr) | (mom > 0.0)
        exit_setup = exit_long | exit_short

        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)


# OPTIMIZATION_V2_COMPLETED
