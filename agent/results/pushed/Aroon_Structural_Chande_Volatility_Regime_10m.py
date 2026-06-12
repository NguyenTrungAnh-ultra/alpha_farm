from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Parameter declarations
        self.aroon_period = int(getattr(self, 'aroon_period', 20))
        self.aroon_min = float(getattr(self, 'aroon_min', 25.0))
        self.cmo_period = int(getattr(self, 'cmo_period', 11))
        self.cmo_trigger = float(getattr(self, 'cmo_trigger', 10.0))
        self.expansion_mult = float(getattr(self, 'expansion_mult', 1.05))
        self.exit_period = int(getattr(self, 'exit_period', 20))
        
        # 2. Local variables for parameters
        aroon_period = self.aroon_period
        aroon_min = self.aroon_min
        cmo_period = self.cmo_period
        cmo_trigger = self.cmo_trigger
        expansion_mult = self.expansion_mult
        exit_period = self.exit_period
        
        # 3. Inputs
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        volume = self.data.pv_volume
        
        # 4. Indicators
        Aroon_Osc = self.feat.aroonosc(high, low, timeperiod=aroon_period)
        CMO = self.feat.cmo(close, timeperiod=cmo_period)
        Volatility_Fast = self.feat.stddev(close, timeperiod=10)
        Volatility_Base = self.feat.sma(Volatility_Fast, timeperiod=30)
        ATR = self.feat.atr(high, low, close, timeperiod=14)
        Midprice_Exit = self.feat.midprice(high, low, timeperiod=exit_period)
        
        # 5. Entry logic
        long_setup = (Aroon_Osc > aroon_min) & (CMO > cmo_trigger) & (Volatility_Fast > Volatility_Base * expansion_mult)
        short_setup = (Aroon_Osc < -aroon_min) & (CMO < -cmo_trigger) & (Volatility_Fast > Volatility_Base * expansion_mult)
        
        # 6. Exit logic
        exit_long = (close < Midprice_Exit - 0.5 * ATR) | (CMO < 0.0)
        exit_short = (close > Midprice_Exit + 0.5 * ATR) | (CMO > 0.0)
        exit_setup = exit_long | exit_short
        
        # 7. Set positions (EXIT first, ENTRY second)
        self.set_positions(exit_setup, position=0.0)
        self.set_positions(long_setup, position=1.0)
        self.set_positions(short_setup, position=-1.0)
