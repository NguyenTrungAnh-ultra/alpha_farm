# Analysis of Performance by Strategy Parameter Count (Timeframes > 5m)

This report evaluates how the number of parameters in a strategy affects its overall backtest performance on the VN30F1M index, **excluding short-term timeframes (1m, 3m, 5m)**. The metrics are simulated using the local XNOPlatformEmulator.

## Overall Performance Ranking by Parameter Count Group

Ranked by average **Sharpe Ratio** (higher is better):

| Rank | Param Count | Strategy Count | Avg Sharpe | Avg CAGR | Avg MaxDD | Avg Profit Factor | Avg Win Rate | Avg Return | Pass Rate (Criteria) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | **0 params** | 1 | 2.144 | 15.52% | -9.80% | 1.363 | 39.36% | 89.95% | 100.0% |
| 2 | **6 params** | 20 | 1.178 | 32.70% | -28.62% | inf | 42.33% | 325.49% | 35.0% |
| 3 | **3 params** | 3 | 0.691 | 20.64% | -5.36% | inf | 12.52% | 251.02% | 33.3% |
| 4 | **5 params** | 17 | 0.651 | 18.31% | -27.68% | inf | 44.01% | 170.09% | 11.8% |
| 5 | **7 params** | 5 | 0.553 | 9.50% | -20.46% | inf | 40.89% | 54.76% | 0.0% |
| 6 | **4 params** | 7 | 0.551 | 20.35% | -29.51% | inf | 29.47% | 192.88% | 28.6% |
| 7 | **8 params** | 4 | 0.345 | 15.97% | -26.27% | 15.575 | 49.24% | 161.29% | 25.0% |

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

### 3 Parameters Group (3 strategies)

- **Avg Sharpe Ratio:** 0.691
- **Avg CAGR:** 20.64%
- **Avg Max Drawdown:** -5.36%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 12.52%
- **Avg Cumulative Return:** 251.02%
- **Pass Rate of Competition Criteria:** 33.3% (0 out of 3 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Triple_Moving_Average_ADX_Regime_Position_30m.py (Sharpe: 2.07, CAGR: 61.9%)
2. Donchian_SAR_Breakout_Confluence_30m.py (Sharpe: 0.00, CAGR: 0.0%)
3. Volatility_Asymmetric_Donchian_Breakout_10m.py (Sharpe: 0.00, CAGR: 0.0%)

### 4 Parameters Group (7 strategies)

- **Avg Sharpe Ratio:** 0.551
- **Avg CAGR:** 20.35%
- **Avg Max Drawdown:** -29.51%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 29.47%
- **Avg Cumulative Return:** 192.88%
- **Pass Rate of Competition Criteria:** 28.6% (2 out of 7 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Session_Williams_R_Volatility_Squeeze_15m.py (Sharpe: 2.04, CAGR: 56.8%)
2. DX_T3_Trend_Strength_10m.py (Sharpe: 1.61, CAGR: 52.6%)
3. APO_SAR_Confluence_Trend_15m.py (Sharpe: 0.66, CAGR: 33.1%)

### 5 Parameters Group (17 strategies)

- **Avg Sharpe Ratio:** 0.651
- **Avg CAGR:** 18.31%
- **Avg Max Drawdown:** -27.68%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 44.01%
- **Avg Cumulative Return:** 170.09%
- **Pass Rate of Competition Criteria:** 11.8% (1 out of 17 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Chande_Volatility_Index_Structural_Regime_30m.py (Sharpe: 2.13, CAGR: 55.7%)
2. Slope_CMO_ADXR_Trend_10m.py (Sharpe: 1.74, CAGR: 50.4%)
3. OBV_Accumulation_ADX_Trend_System_10m.py (Sharpe: 1.28, CAGR: 46.0%)

### 6 Parameters Group (20 strategies)

- **Avg Sharpe Ratio:** 1.178
- **Avg CAGR:** 32.70%
- **Avg Max Drawdown:** -28.62%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 42.33%
- **Avg Cumulative Return:** 325.49%
- **Pass Rate of Competition Criteria:** 35.0% (7 out of 20 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. MACD_Histogram_Slope_Position_Follower_30m.py (Sharpe: 2.27, CAGR: 73.5%)
2. Triple_Exponential_CCI_Volatility_Regime_10m.py (Sharpe: 2.26, CAGR: 59.7%)
3. Linear_Slope_CCI_Regime_Position_30m.py (Sharpe: 2.13, CAGR: 49.7%)

### 7 Parameters Group (5 strategies)

- **Avg Sharpe Ratio:** 0.553
- **Avg CAGR:** 9.50%
- **Avg Max Drawdown:** -20.46%
- **Avg Profit Factor:** inf
- **Avg Win Rate:** 40.89%
- **Avg Cumulative Return:** 54.76%
- **Pass Rate of Competition Criteria:** 0.0% (0 out of 5 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. LinearReg_Channel_ADX_Breakout_30m.py (Sharpe: 1.07, CAGR: 11.5%)
2. TRIX_ADX_Trail_System_10m.py (Sharpe: 0.70, CAGR: 4.3%)
3. Chande_Momentum_Oscillator_DEMA_Swing_15m.py (Sharpe: 0.62, CAGR: 21.1%)

### 8 Parameters Group (4 strategies)

- **Avg Sharpe Ratio:** 0.345
- **Avg CAGR:** 15.97%
- **Avg Max Drawdown:** -26.27%
- **Avg Profit Factor:** 15.575
- **Avg Win Rate:** 49.24%
- **Avg Cumulative Return:** 161.29%
- **Pass Rate of Competition Criteria:** 25.0% (1 out of 4 strategies passed)

**Top 3 Strategies in this Group (by Sharpe):**
1. Absolute_Price_Oscillator_Volatility_Enforcer_10m.py (Sharpe: 1.47, CAGR: 49.6%)
2. PPO_Bandwidth_Expansion_Strategy_30m.py (Sharpe: 0.63, CAGR: 26.5%)
3. ROC_BBWidth_Momentum_System_10m.py (Sharpe: 0.48, CAGR: 2.5%)

## Error Logs during Backtesting

- **Star_Reversal_ADX_Trail_10m.py**: strategy verification failed: 'self.feat' has no method 'cdlmorningstar'.