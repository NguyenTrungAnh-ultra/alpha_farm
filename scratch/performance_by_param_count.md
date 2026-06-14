# Analysis of Performance by Strategy Parameter Count

This report evaluates how the number of parameters in a strategy affects its overall backtest performance on the VN30F1M index. The metrics are simulated using the local XNOPlatformEmulator.

## Overall Performance Ranking by Parameter Count Group

Ranked by average **Sharpe Ratio** (higher is better):

| Rank | Param Count | Strategy Count | Avg Sharpe | Avg CAGR | Avg MaxDD | Avg Profit Factor | Avg Win Rate | Avg Return | Pass Rate (Criteria) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **0 params** | 1 | 2.144 | 15.52% | -9.80% | 1.363 | 39.36% | 89.95% | 100.0% |
| 2 | **6 params** | 28 | 0.893 | 27.08% | -31.93% | inf | 42.40% | 283.15% | 32.1% |
| 3 | **7 params** | 11 | 0.221 | 12.79% | -64.04% | inf | 41.26% | 86.26% | 18.2% |
| 4 | **5 params** | 31 | -0.182 | 15.24% | -130.27% | inf | 40.08% | 29.07% | 6.5% |
| 5 | **4 params** | 15 | -0.341 | 16.15% | -196.21% | inf | 31.14% | 8.42% | 20.0% |
| 6 | **3 params** | 5 | -0.550 | 12.38% | -251.90% | inf | 28.59% | -97.35% | 20.0% |
| 7 | **8 params** | 6 | -0.585 | 10.68% | -196.43% | inf | 55.66% | -67.56% | 16.7% |
| 8 | **9 params** | 1 | -1.645 | 0.00% | -383.31% | 0.937 | 39.44% | -322.62% | 0.0% |

## Detailed Analysis by Parameter Group

### 0 Parameters Group (1 strategies)

- **Avg Sharpe Ratio:** 2.144
- **Avg CAGR:** 15.52%
- **Avg Max Drawdown:** -9.80%
- **Avg Profit Factor:** 1.363
- **Avg Win Rate:** 39.36%
- **Avg Cumulative Return:** 89.95%
- **Pass Rate of Competition Criteria:** 100.0% (1 out of 1 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. WQ_Alpha5_10m.py (Sharpe: 2.14, CAGR: 15.5%)

### 3 Parameters Group (5 strategies)

- **Avg Sharpe Ratio:** -0.550
- **Avg CAGR:** 12.38%
- **Avg Max Drawdown:** -251.90%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 28.59%
- **Avg Cumulative Return:** -97.35%
- **Pass Rate of Competition Criteria:** 20.0% (1 out of 5 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Triple_Moving_Average_ADX_Regime_Position_30m.py (Sharpe: 2.07, CAGR: 61.9%)
2. Donchian_SAR_Breakout_Confluence_30m.py (Sharpe: 0.00, CAGR: 0.0%)
3. Volatility_Asymmetric_Donchian_Breakout_10m.py (Sharpe: 0.00, CAGR: 0.0%)

### 4 Parameters Group (15 strategies)

- **Avg Sharpe Ratio:** -0.341
- **Avg CAGR:** 16.15%
- **Avg Max Drawdown:** -196.21%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 31.14%
- **Avg Cumulative Return:** 8.42%
- **Pass Rate of Competition Criteria:** 20.0% (3 out of 15 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Session_Williams_R_Volatility_Squeeze_15m.py (Sharpe: 2.04, CAGR: 56.8%)
2. Kama_Trend_Plus_DI_Breakout_5m.py (Sharpe: 1.81, CAGR: 61.6%)
3. DX_T3_Trend_Strength_10m.py (Sharpe: 1.61, CAGR: 52.6%)

### 5 Parameters Group (31 strategies)

- **Avg Sharpe Ratio:** -0.182
- **Avg CAGR:** 15.24%
- **Avg Max Drawdown:** -130.27%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 40.08%
- **Avg Cumulative Return:** 29.07%
- **Pass Rate of Competition Criteria:** 6.5% (2 out of 31 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Chande_Volatility_Index_Structural_Regime_30m.py (Sharpe: 2.13, CAGR: 55.7%)
2. Triangular_Aroon_Trend_Follower_5m.py (Sharpe: 1.84, CAGR: 64.1%)
3. Hull_Linear_Acceleration_Trend_5m.py (Sharpe: 1.74, CAGR: 60.5%)

### 6 Parameters Group (28 strategies)

- **Avg Sharpe Ratio:** 0.893
- **Avg CAGR:** 27.08%
- **Avg Max Drawdown:** -31.93%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 42.40%
- **Avg Cumulative Return:** 283.15%
- **Pass Rate of Competition Criteria:** 32.1% (9 out of 28 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. MACD_Histogram_Slope_Position_Follower_30m.py (Sharpe: 2.27, CAGR: 73.5%)
2. Triple_Exponential_CCI_Volatility_Regime_10m.py (Sharpe: 2.26, CAGR: 59.7%)
3. Linear_Slope_CCI_Regime_Position_30m.py (Sharpe: 2.13, CAGR: 49.7%)

### 7 Parameters Group (11 strategies)

- **Avg Sharpe Ratio:** 0.221
- **Avg CAGR:** 12.79%
- **Avg Max Drawdown:** -64.04%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 41.26%
- **Avg Cumulative Return:** 86.26%
- **Pass Rate of Competition Criteria:** 18.2% (2 out of 11 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Keltner_Adaptive_Trend_Breakout_5m.py (Sharpe: 2.25, CAGR: 57.4%)
2. PPO_CMO_ATR_Trail_5m.py (Sharpe: 1.87, CAGR: 51.5%)
3. LinearReg_Channel_ADX_Breakout_30m.py (Sharpe: 1.07, CAGR: 11.5%)

### 8 Parameters Group (6 strategies)

- **Avg Sharpe Ratio:** -0.585
- **Avg CAGR:** 10.68%
- **Avg Max Drawdown:** -196.43%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 55.66%
- **Avg Cumulative Return:** -67.56%
- **Pass Rate of Competition Criteria:** 16.7% (0 out of 6 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Absolute_Price_Oscillator_Volatility_Enforcer_10m.py (Sharpe: 1.47, CAGR: 49.6%)
2. PPO_Bandwidth_Expansion_Strategy_30m.py (Sharpe: 0.63, CAGR: 26.5%)
3. ROC_BBWidth_Momentum_System_10m.py (Sharpe: 0.48, CAGR: 2.5%)

### 9 Parameters Group (1 strategies)

- **Avg Sharpe Ratio:** -1.645
- **Avg CAGR:** 0.00%
- **Avg Max Drawdown:** -383.31%
- **Avg Profit Factor:** 0.937
- **Avg Win Rate:** 39.44%
- **Avg Cumulative Return:** -322.62%
- **Pass Rate of Competition Criteria:** 0.0% (0 out of 1 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Micro_DEMA_ADXR_Volume_Scalper_1m.py (Sharpe: -1.65, CAGR: 0.0%)

## Error Logs during Backtesting

- **Star_Reversal_ADX_Trail_10m.py**: strategy verification failed: 'self.feat' has no method 'cdlmorningstar'.