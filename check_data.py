"""
Test: TA-Lib indicators vs Manual indicators vs XNOQuant
Strategy: EMA(8/21) + RSI(14) + ATR(14) (Strategy B đã verify exact)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import talib

from backtest.engine import XNOBacktestEngine, load_data
from backtest.strategy import SimpleAlgorithm
from backtest.indicators import FeatureEngine
from backtest.metrics import compute_metrics


# === TA-Lib version of FeatureEngine ===
class TALibFeatureEngine:
    """FeatureEngine dùng TA-Lib thay vì tính tay."""
    
    @staticmethod
    def sma(series, timeperiod):
        return pd.Series(talib.SMA(series.values.astype(float), timeperiod=timeperiod), index=series.index)
    
    @staticmethod
    def ema(series, timeperiod):
        return pd.Series(talib.EMA(series.values.astype(float), timeperiod=timeperiod), index=series.index)
    
    @staticmethod
    def rsi(series, timeperiod):
        return pd.Series(talib.RSI(series.values.astype(float), timeperiod=timeperiod), index=series.index)
    
    @staticmethod
    def atr(high, low, close, timeperiod):
        return pd.Series(talib.ATR(high.values.astype(float), low.values.astype(float), 
                                    close.values.astype(float), timeperiod=timeperiod), index=close.index)
    
    @staticmethod
    def adx(high, low, close, timeperiod):
        return pd.Series(talib.ADX(high.values.astype(float), low.values.astype(float),
                                    close.values.astype(float), timeperiod=timeperiod), index=close.index)
    
    @staticmethod
    def stddev(series, timeperiod):
        return pd.Series(talib.STDDEV(series.values.astype(float), timeperiod=timeperiod, nbdev=1), index=series.index)
    
    @staticmethod
    def roc(series, timeperiod):
        return pd.Series(talib.ROC(series.values.astype(float), timeperiod=timeperiod), index=series.index)
    
    @staticmethod
    def rolling_mean(series, timeperiod):
        return pd.Series(talib.SMA(series.values.astype(float), timeperiod=timeperiod), index=series.index)


# === Strategy B with manual indicators ===
class StratB_Manual(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        ema8 = self.feat.ema(close, timeperiod=8)
        ema21 = self.feat.ema(close, timeperiod=21)
        rsi = self.feat.rsi(close, 14)
        atr = self.feat.atr(high, low, close, 14)
        atr_avg = self.feat.sma(atr, timeperiod=50)
        vol_ok = atr > atr_avg
        long_zone = (ema8 > ema21) & (rsi > 50) & (rsi < 70) & vol_ok
        short_zone = (ema8 < ema21) & (rsi > 30) & (rsi < 50) & vol_ok
        flat_zone = ~long_zone & ~short_zone
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)


# === Strategy B with TA-Lib indicators ===
class StratB_TALib(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        high = self.data.pv_high
        low = self.data.pv_low
        feat = TALibFeatureEngine()
        ema8 = feat.ema(close, timeperiod=8)
        ema21 = feat.ema(close, timeperiod=21)
        rsi = feat.rsi(close, 14)
        atr = feat.atr(high, low, close, 14)
        atr_avg = feat.sma(atr, timeperiod=50)
        vol_ok = atr > atr_avg
        long_zone = (ema8 > ema21) & (rsi > 50) & (rsi < 70) & vol_ok
        short_zone = (ema8 < ema21) & (rsi > 30) & (rsi < 50) & vol_ok
        flat_zone = ~long_zone & ~short_zone
        self.set_positions(flat_zone, position=0.0)
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)


engine = XNOBacktestEngine()

# XNO reference (verified exact on all TFs)
xno_ref = {
    '1m':  {'trades': 39086, 'fees': 965.02, 'equity': -3_332_160_000},
    '5m':  {'trades': 6923,  'fees': 170.04, 'equity': 1_840_000_000},
    '10m': {'trades': 3935,  'fees': 97.10,  'equity': 1_650_560_000},
    '15m': {'trades': 2838,  'fees': 69.41,  'equity': 1_407_920_000},
    '30m': {'trades': 1465,  'fees': 36.19,  'equity': 702_080_000},
}

print("=" * 100)
print("  Strategy B: EMA(8/21)+RSI(14)+ATR(14) — Manual vs TA-Lib vs XNO")
print("=" * 100)
print(f"\n  {'TF':>4} │ {'':^38} │ {'':^38} │")
print(f"  {'':>4} │ {'MANUAL (tự viết)':^38} │ {'TA-LIB':^38} │ {'XNO':^14}")
print(f"  {'':>4} │ {'Trades':>7} {'Fees%':>9} {'Equity':>18} │ {'Trades':>7} {'Fees%':>9} {'Equity':>18} │ {'Match?':^14}")
print(f"  {'─' * 95}")

import time

for tf in ['1m', '5m', '15m', '30m']:
    df = load_data(tf)
    ref = xno_ref.get(tf, {})
    
    # Manual
    t0 = time.time()
    r_manual = engine.run(StratB_Manual(), df)
    t_manual = time.time() - t0
    m_manual = compute_metrics(r_manual)
    
    # TA-Lib
    t0 = time.time()
    r_talib = engine.run(StratB_TALib(), df)
    t_talib = time.time() - t0
    m_talib = compute_metrics(r_talib)
    
    # Compare
    trades_match = m_manual['total_trades'] == m_talib['total_trades']
    equity_match = m_manual['net_equity'] == m_talib['net_equity']
    xno_match = ""
    if ref:
        xno_match = "✅" if m_talib['total_trades'] == ref['trades'] and int(m_talib['net_equity']) == ref['equity'] else "❌"
    
    same = "✅ SAME" if trades_match and equity_match else "❌ DIFF"
    
    print(f"  {tf:>4} │ {m_manual['total_trades']:>7} {m_manual['total_fees_pct']:>8.2f}% {m_manual['net_equity']:>17,.0f} │ "
          f"{m_talib['total_trades']:>7} {m_talib['total_fees_pct']:>8.2f}% {m_talib['net_equity']:>17,.0f} │ {xno_match:^14}")

print(f"\n  {'─' * 95}")

# === Speed comparison on 1m (272k bars) ===
print(f"\n  ⏱ Tốc độ trên 1m (272k bars):")
df = load_data('1m')

t0 = time.time()
engine.run(StratB_Manual(), df)
print(f"    Manual: {time.time() - t0:.2f}s")

t0 = time.time()
engine.run(StratB_TALib(), df)
print(f"    TA-Lib: {time.time() - t0:.2f}s")

# === Indicator value comparison ===
print(f"\n  📊 So sánh giá trị indicator (1m, bar 100-105):")
df = load_data('1m')
close = df['Close']
high = df['High']
low = df['Low']

manual_feat = FeatureEngine()
talib_feat = TALibFeatureEngine()

for name, m_fn, t_fn in [
    ('EMA(8)',  lambda: manual_feat.ema(close, 8),  lambda: talib_feat.ema(close, 8)),
    ('RSI(14)', lambda: manual_feat.rsi(close, 14), lambda: talib_feat.rsi(close, 14)),
    ('ATR(14)', lambda: manual_feat.atr(high, low, close, 14), lambda: talib_feat.atr(high, low, close, 14)),
]:
    m_vals = m_fn()
    t_vals = t_fn()
    print(f"\n    {name}:")
    for i in range(100, 106):
        m_v = m_vals.iloc[i]
        t_v = t_vals.iloc[i]
        diff = abs(m_v - t_v) if not (np.isnan(m_v) or np.isnan(t_v)) else 0
        print(f"      [{i}] Manual={m_v:.6f}  TALib={t_v:.6f}  Δ={diff:.8f}")
