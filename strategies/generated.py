"""
Strategy Library — 10 Diverse Strategies for VN30F1M
=====================================================
Each strategy uses talib pre-computed indicators and inherits BaseStrategy.
Designed for maximum diversity (low inter-strategy correlation).

Families:
    Trend-Following:  EmaCrossADX, DemaTrend, SarADX
    Momentum:         MACDHist, TrixCross
    Mean-Reversion:   RSIReversion
    Breakout:         BollingerBreak, DonchianBreak, KeltnerBreak
    Multi-Indicator:  StochCCI
"""

import talib
import numpy as np
import pandas as pd
from backtest.strategy import BaseStrategy
from backtest.engine import Signal


# ═══════════════════════════════════════════════════════════════════════
# 1. EMA Crossover + ADX Filter  (Trend-Following)
# ═══════════════════════════════════════════════════════════════════════

class EmaCrossADX(BaseStrategy):
    """
    EMA fast/slow crossover, only trade when ADX confirms strong trend.

    Entry : EMA_fast > EMA_slow AND ADX > threshold → LONG (vice-versa SHORT)
    Exit  : Direction flips OR ADX drops below threshold.
    """

    def __init__(self, ema_fast=10, ema_slow=30, adx_period=14, adx_threshold=25.0):
        super().__init__()
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.params = dict(ema_fast=ema_fast, ema_slow=ema_slow,
                           adx_period=adx_period, adx_threshold=adx_threshold)
        self._ef = self._es = self._adx = None

    def setup(self, data):
        c = data['Close'].values.astype(np.float64)
        h = data['High'].values.astype(np.float64)
        l = data['Low'].values.astype(np.float64)
        idx = data.index
        self._ef  = dict(zip(idx, talib.EMA(c, timeperiod=self.ema_fast)))
        self._es  = dict(zip(idx, talib.EMA(c, timeperiod=self.ema_slow)))
        self._adx = dict(zip(idx, talib.ADX(h, l, c, timeperiod=self.adx_period)))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        ef, es, adx = self._ef.get(i, np.nan), self._es.get(i, np.nan), self._adx.get(i, np.nan)
        if np.isnan(ef) or np.isnan(adx):
            return Signal.FLAT
        if adx > self.adx_threshold:
            if ef > es: return Signal.LONG
            if ef < es: return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        i = bar.name
        ef, es, adx = self._ef.get(i, np.nan), self._es.get(i, np.nan), self._adx.get(i, np.nan)
        if np.isnan(ef) or np.isnan(adx):
            return False
        if adx <= self.adx_threshold:
            return True
        if position.direction == 1 and ef < es:
            return True
        if position.direction == -1 and ef > es:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 2. DEMA Trend  (Trend-Following — different smoothing from EMA)
# ═══════════════════════════════════════════════════════════════════════

class DemaTrend(BaseStrategy):
    """
    Double EMA (DEMA) fast/slow crossover.
    DEMA responds faster than EMA to price changes.

    Entry : DEMA_fast > DEMA_slow → LONG (vice-versa SHORT)
    Exit  : Direction flips.
    """

    def __init__(self, dema_fast=8, dema_slow=30):
        super().__init__()
        self.dema_fast = dema_fast
        self.dema_slow = dema_slow
        self.params = dict(dema_fast=dema_fast, dema_slow=dema_slow)
        self._df = self._ds = None

    def setup(self, data):
        c = data['Close'].values.astype(np.float64)
        idx = data.index
        self._df = dict(zip(idx, talib.DEMA(c, timeperiod=self.dema_fast)))
        self._ds = dict(zip(idx, talib.DEMA(c, timeperiod=self.dema_slow)))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        df, ds = self._df.get(i, np.nan), self._ds.get(i, np.nan)
        if np.isnan(df) or np.isnan(ds):
            return Signal.FLAT
        if df > ds: return Signal.LONG
        if df < ds: return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        i = bar.name
        df, ds = self._df.get(i, np.nan), self._ds.get(i, np.nan)
        if np.isnan(df) or np.isnan(ds):
            return False
        if position.direction == 1 and df < ds:
            return True
        if position.direction == -1 and df > ds:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 3. Parabolic SAR + ADX  (Trend-Following — different mechanism)
# ═══════════════════════════════════════════════════════════════════════

class SarADX(BaseStrategy):
    """
    Parabolic SAR for direction + ADX for trend strength filter.

    Entry : Close > SAR AND ADX > threshold → LONG (vice-versa SHORT)
    Exit  : SAR flips OR ADX drops.
    """

    def __init__(self, sar_accel=0.02, sar_maximum=0.2, adx_period=14, adx_threshold=25.0):
        super().__init__()
        self.sar_accel = sar_accel
        self.sar_maximum = sar_maximum
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.params = dict(sar_accel=sar_accel, sar_maximum=sar_maximum,
                           adx_period=adx_period, adx_threshold=adx_threshold)
        self._sar = self._adx = None

    def setup(self, data):
        h = data['High'].values.astype(np.float64)
        l = data['Low'].values.astype(np.float64)
        c = data['Close'].values.astype(np.float64)
        idx = data.index
        self._sar = dict(zip(idx, talib.SAR(h, l,
                              acceleration=self.sar_accel, maximum=self.sar_maximum)))
        self._adx = dict(zip(idx, talib.ADX(h, l, c, timeperiod=self.adx_period)))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        sar, adx = self._sar.get(i, np.nan), self._adx.get(i, np.nan)
        close = bar['Close']
        if np.isnan(sar) or np.isnan(adx):
            return Signal.FLAT
        if adx > self.adx_threshold:
            if close > sar: return Signal.LONG
            if close < sar: return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        i = bar.name
        sar, adx = self._sar.get(i, np.nan), self._adx.get(i, np.nan)
        close = bar['Close']
        if np.isnan(sar) or np.isnan(adx):
            return False
        if adx <= self.adx_threshold:
            return True
        if position.direction == 1 and close < sar:
            return True
        if position.direction == -1 and close > sar:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 4. MACD Histogram  (Momentum)
# ═══════════════════════════════════════════════════════════════════════

class MACDHist(BaseStrategy):
    """
    MACD Histogram direction as momentum signal.

    Entry : MACD histogram > 0 → LONG; < 0 → SHORT
    Exit  : Histogram flips sign.
    """

    def __init__(self, macd_fast=12, macd_slow=26, macd_signal=9):
        super().__init__()
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.params = dict(macd_fast=macd_fast, macd_slow=macd_slow,
                           macd_signal=macd_signal)
        self._hist = None

    def setup(self, data):
        c = data['Close'].values.astype(np.float64)
        idx = data.index
        _, _, hist = talib.MACD(c, fastperiod=self.macd_fast,
                                slowperiod=self.macd_slow,
                                signalperiod=self.macd_signal)
        self._hist = dict(zip(idx, hist))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        h = self._hist.get(bar.name, np.nan)
        if np.isnan(h):
            return Signal.FLAT
        if h > 0: return Signal.LONG
        if h < 0: return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        h = self._hist.get(bar.name, np.nan)
        if np.isnan(h):
            return False
        if position.direction == 1 and h < 0:
            return True
        if position.direction == -1 and h > 0:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 5. TRIX Crossover  (Momentum — triple-smoothed, different from MACD)
# ═══════════════════════════════════════════════════════════════════════

class TrixCross(BaseStrategy):
    """
    TRIX line vs its SMA signal line.
    TRIX = 1-period rate-of-change of a triple-smoothed EMA.

    Entry : TRIX > signal → LONG; TRIX < signal → SHORT
    Exit  : Crossover flips.
    """

    def __init__(self, trix_period=15, signal_period=9):
        super().__init__()
        self.trix_period = trix_period
        self.signal_period = signal_period
        self.params = dict(trix_period=trix_period, signal_period=signal_period)
        self._trix = self._sig = None

    def setup(self, data):
        c = data['Close'].values.astype(np.float64)
        idx = data.index
        trix = talib.TRIX(c, timeperiod=self.trix_period)
        sig  = talib.SMA(trix, timeperiod=self.signal_period)
        self._trix = dict(zip(idx, trix))
        self._sig  = dict(zip(idx, sig))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        t, s = self._trix.get(i, np.nan), self._sig.get(i, np.nan)
        if np.isnan(t) or np.isnan(s):
            return Signal.FLAT
        if t > s: return Signal.LONG
        if t < s: return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        i = bar.name
        t, s = self._trix.get(i, np.nan), self._sig.get(i, np.nan)
        if np.isnan(t) or np.isnan(s):
            return False
        if position.direction == 1 and t < s:
            return True
        if position.direction == -1 and t > s:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 6. RSI Mean Reversion + EMA Trend Filter  (Mean-Reversion)
# ═══════════════════════════════════════════════════════════════════════

class RSIReversion(BaseStrategy):
    """
    Buy oversold / sell overbought, but only when aligned with the trend (EMA filter).

    Entry : RSI < oversold AND close > EMA → LONG  (dip-buy in uptrend)
            RSI > overbought AND close < EMA → SHORT (rally-sell in downtrend)
    Exit  : RSI returns to neutral zone (crosses 50).
    """

    def __init__(self, rsi_period=14, rsi_oversold=30, rsi_overbought=70, ema_period=50):
        super().__init__()
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.ema_period = ema_period
        self.params = dict(rsi_period=rsi_period, rsi_oversold=rsi_oversold,
                           rsi_overbought=rsi_overbought, ema_period=ema_period)
        self._rsi = self._ema = None

    def setup(self, data):
        c = data['Close'].values.astype(np.float64)
        idx = data.index
        self._rsi = dict(zip(idx, talib.RSI(c, timeperiod=self.rsi_period)))
        self._ema = dict(zip(idx, talib.EMA(c, timeperiod=self.ema_period)))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        rsi, ema = self._rsi.get(i, np.nan), self._ema.get(i, np.nan)
        close = bar['Close']
        if np.isnan(rsi) or np.isnan(ema):
            return Signal.FLAT
        if rsi < self.rsi_oversold and close > ema:
            return Signal.LONG
        if rsi > self.rsi_overbought and close < ema:
            return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        rsi = self._rsi.get(bar.name, np.nan)
        if np.isnan(rsi):
            return False
        # Exit when RSI returns to neutral
        if position.direction == 1 and rsi > 50:
            return True
        if position.direction == -1 and rsi < 50:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 7. Bollinger Band Breakout  (Volatility Breakout)
# ═══════════════════════════════════════════════════════════════════════

class BollingerBreak(BaseStrategy):
    """
    Momentum breakout through Bollinger Bands.

    Entry : Close > Upper Band → LONG; Close < Lower Band → SHORT
    Exit  : Close crosses back below/above Middle Band.
    """

    def __init__(self, bb_period=20, bb_std=2.0):
        super().__init__()
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.params = dict(bb_period=bb_period, bb_std=bb_std)
        self._upper = self._middle = self._lower = None

    def setup(self, data):
        c = data['Close'].values.astype(np.float64)
        idx = data.index
        upper, middle, lower = talib.BBANDS(c, timeperiod=self.bb_period,
                                            nbdevup=self.bb_std, nbdevdn=self.bb_std,
                                            matype=0)
        self._upper  = dict(zip(idx, upper))
        self._middle = dict(zip(idx, middle))
        self._lower  = dict(zip(idx, lower))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        u = self._upper.get(i, np.nan)
        l = self._lower.get(i, np.nan)
        close = bar['Close']
        if np.isnan(u):
            return Signal.FLAT
        if close > u: return Signal.LONG
        if close < l: return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        m = self._middle.get(bar.name, np.nan)
        close = bar['Close']
        if np.isnan(m):
            return False
        if position.direction == 1 and close < m:
            return True
        if position.direction == -1 and close > m:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 8. Donchian Channel Breakout  (Price Channel Breakout)
# ═══════════════════════════════════════════════════════════════════════

class DonchianBreak(BaseStrategy):
    """
    Price breaks N-period high/low channel (Turtle Trading style).

    Entry : Close > Highest High of N bars → LONG
            Close < Lowest Low of N bars → SHORT
    Exit  : Close crosses back to channel midpoint.
    """

    def __init__(self, donchian_period=20):
        super().__init__()
        self.donchian_period = donchian_period
        self.params = dict(donchian_period=donchian_period)
        self._upper = self._lower = self._middle = None

    def setup(self, data):
        idx = data.index
        high_s = pd.Series(data['High'].values).rolling(self.donchian_period).max().values
        low_s  = pd.Series(data['Low'].values).rolling(self.donchian_period).min().values
        mid_s  = (high_s + low_s) / 2
        self._upper  = dict(zip(idx, high_s))
        self._lower  = dict(zip(idx, low_s))
        self._middle = dict(zip(idx, mid_s))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        u = self._upper.get(i, np.nan)
        l = self._lower.get(i, np.nan)
        close = bar['Close']
        if np.isnan(u):
            return Signal.FLAT
        if close > u: return Signal.LONG
        if close < l: return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        m = self._middle.get(bar.name, np.nan)
        close = bar['Close']
        if np.isnan(m):
            return False
        if position.direction == 1 and close < m:
            return True
        if position.direction == -1 and close > m:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 9. Keltner Channel Breakout  (Volatility-Adjusted Breakout)
# ═══════════════════════════════════════════════════════════════════════

class KeltnerBreak(BaseStrategy):
    """
    Keltner Channel = EMA ± multiplier * ATR.
    Breakout outside the channel signals strong momentum.

    Entry : Close > Upper Keltner → LONG; Close < Lower Keltner → SHORT
    Exit  : Close crosses back inside to EMA.
    """

    def __init__(self, ema_period=20, atr_period=14, atr_mult=1.5):
        super().__init__()
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.params = dict(ema_period=ema_period, atr_period=atr_period,
                           atr_mult=atr_mult)
        self._ema = self._upper = self._lower = None

    def setup(self, data):
        h = data['High'].values.astype(np.float64)
        l = data['Low'].values.astype(np.float64)
        c = data['Close'].values.astype(np.float64)
        idx = data.index
        ema = talib.EMA(c, timeperiod=self.ema_period)
        atr = talib.ATR(h, l, c, timeperiod=self.atr_period)
        self._ema   = dict(zip(idx, ema))
        self._upper = dict(zip(idx, ema + self.atr_mult * atr))
        self._lower = dict(zip(idx, ema - self.atr_mult * atr))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        u = self._upper.get(i, np.nan)
        l = self._lower.get(i, np.nan)
        close = bar['Close']
        if np.isnan(u):
            return Signal.FLAT
        if close > u: return Signal.LONG
        if close < l: return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        ema = self._ema.get(bar.name, np.nan)
        close = bar['Close']
        if np.isnan(ema):
            return False
        if position.direction == 1 and close < ema:
            return True
        if position.direction == -1 and close > ema:
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════
# 10. Stochastic + CCI Combo  (Multi-Indicator)
# ═══════════════════════════════════════════════════════════════════════

class StochCCI(BaseStrategy):
    """
    Two uncorrelated oscillators must agree for entry (higher confidence).

    Entry : Stoch %K > %D AND CCI > 0 → LONG
            Stoch %K < %D AND CCI < 0 → SHORT
    Exit  : Either indicator disagrees with position direction.
    """

    def __init__(self, stoch_k=14, stoch_d=3, cci_period=20):
        super().__init__()
        self.stoch_k = stoch_k
        self.stoch_d = stoch_d
        self.cci_period = cci_period
        self.params = dict(stoch_k=stoch_k, stoch_d=stoch_d, cci_period=cci_period)
        self._sk = self._sd = self._cci = None

    def setup(self, data):
        h = data['High'].values.astype(np.float64)
        l = data['Low'].values.astype(np.float64)
        c = data['Close'].values.astype(np.float64)
        idx = data.index
        slowk, slowd = talib.STOCH(h, l, c,
                                   fastk_period=self.stoch_k,
                                   slowk_period=self.stoch_d,
                                   slowk_matype=0,
                                   slowd_period=self.stoch_d,
                                   slowd_matype=0)
        self._sk  = dict(zip(idx, slowk))
        self._sd  = dict(zip(idx, slowd))
        self._cci = dict(zip(idx, talib.CCI(h, l, c, timeperiod=self.cci_period)))

    def on_bar(self, bar):
        pass

    def generate_signal(self, bar):
        i = bar.name
        sk  = self._sk.get(i, np.nan)
        sd  = self._sd.get(i, np.nan)
        cci = self._cci.get(i, np.nan)
        if np.isnan(sk) or np.isnan(cci):
            return Signal.FLAT
        if sk > sd and cci > 0:
            return Signal.LONG
        if sk < sd and cci < 0:
            return Signal.SHORT
        return Signal.FLAT

    def should_exit(self, bar, position):
        i = bar.name
        sk  = self._sk.get(i, np.nan)
        sd  = self._sd.get(i, np.nan)
        cci = self._cci.get(i, np.nan)
        if np.isnan(sk) or np.isnan(cci):
            return False
        if position.direction == 1:
            if sk < sd or cci < 0:
                return True
        if position.direction == -1:
            if sk > sd or cci > 0:
                return True
        return False
