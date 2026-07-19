# Hidden Markov Model & Monte Carlo Validation Report

This report presents the validation results of representative trading alphas backtested on 100 HMM-guided synthetic price paths, under both **Normal** and **Stressed** market conditions.

## Executive Summary

The objective of HMM-guided Monte Carlo validation is to verify if a strategy's historical backtest performance is structurally robust or represents a lucky path (overfitted to the specific timeline).
- **Historical Sharpe Percentile**: Represents the percentage of synthetic paths where the strategy achieved a Sharpe ratio lower than its historical backtest. A percentile close to **50%** means the backtest is a median expectation. A percentile close to **99%** means the historical run is a highly optimistic outlier.
- **Pass Rate**: The percentage of simulated paths where the strategy satisfies the minimum criteria: **Sharpe >= 1.3** and **Max Drawdown >= -35%**.

## Validation Performance Matrix

| Strategy | Timeframe | Scenario | Historical Sharpe | MC Sharpe (Mean ± Std) | MC Sharpe (5% to 95%) | Historical Percentile | Pass Rate |
|---|---|---|---|---|---|---|---|
| Mcts_Volume_z_Cmo_52a8_15m.py | 15m | Normal | 1.70 | 1.15 ± 0.52 | [0.31, 1.99] | 87.6% | 36.6% |
| Mcts_Volume_z_Cmo_52a8_15m.py | 15m | Stressed | 1.70 | 1.05 ± 0.50 | [0.17, 1.91] | 90.0% | 28.6% |
| Mcts_Rolling_rank_Atr_Rsi_40ed_15m.py | 15m | Normal | 1.35 | 1.00 ± 0.45 | [0.23, 1.75] | 77.4% | 27.0% |
| Mcts_Rolling_rank_Atr_Rsi_40ed_15m.py | 15m | Stressed | 1.35 | 0.85 ± 0.48 | [0.05, 1.63] | 86.4% | 16.0% |
| Mcts_Rolling_rank_Tema_8587_15m.py | 15m | Normal | 1.25 | 1.03 ± 0.49 | [0.30, 1.83] | 68.2% | 28.0% |
| Mcts_Rolling_rank_Tema_8587_15m.py | 15m | Stressed | 1.25 | 1.02 ± 0.51 | [0.20, 1.86] | 67.8% | 27.6% |
| Mcts_Natr_9fda_15m.py | 15m | Normal | 1.18 | 0.43 ± 0.42 | [-0.27, 1.14] | 96.0% | 2.6% |
| Mcts_Natr_9fda_15m.py | 15m | Stressed | 1.18 | 0.34 ± 0.42 | [-0.47, 0.99] | 97.2% | 1.6% |
| Mcts_Natr_a743_15m.py | 15m | Normal | 1.18 | 0.43 ± 0.42 | [-0.27, 1.14] | 96.0% | 2.6% |
| Mcts_Natr_a743_15m.py | 15m | Stressed | 1.18 | 0.34 ± 0.42 | [-0.47, 0.99] | 97.2% | 1.6% |
| Mcts_Rolling_rank_Atr_7002_60m.py | 60m | Normal | 1.14 | 0.58 ± 0.42 | [-0.11, 1.32] | 90.2% | 5.6% |
| Mcts_Rolling_rank_Atr_7002_60m.py | 60m | Stressed | 1.14 | 0.66 ± 0.41 | [-0.00, 1.33] | 87.4% | 6.0% |
| Mcts_Rolling_rank_Atr_60f5_60m.py | 60m | Normal | 1.08 | 0.41 ± 0.49 | [-0.40, 1.18] | 91.8% | 3.0% |
| Mcts_Rolling_rank_Atr_60f5_60m.py | 60m | Stressed | 1.08 | 0.52 ± 0.49 | [-0.26, 1.37] | 85.0% | 6.6% |
| Mcts_Rolling_zscore_Atr_daa4_60m.py | 60m | Normal | 0.98 | 0.51 ± 0.46 | [-0.21, 1.34] | 84.8% | 5.4% |
| Mcts_Rolling_zscore_Atr_daa4_60m.py | 60m | Stressed | 0.98 | 0.59 ± 0.46 | [-0.19, 1.36] | 81.4% | 6.2% |
| Mcts_Rsi_Atr_114b_60m.py | 60m | Normal | 0.97 | 0.44 ± 0.47 | [-0.29, 1.22] | 86.8% | 3.2% |
| Mcts_Rsi_Atr_114b_60m.py | 60m | Stressed | 0.97 | 0.55 ± 0.49 | [-0.22, 1.38] | 79.8% | 6.6% |
| Mcts_Rsi_Atr_3540_60m.py | 60m | Normal | 0.97 | 0.48 ± 0.43 | [-0.18, 1.23] | 87.0% | 3.0% |
| Mcts_Rsi_Atr_3540_60m.py | 60m | Stressed | 0.97 | 0.54 ± 0.45 | [-0.17, 1.31] | 80.2% | 5.4% |


## Strategy Breakdown Analysis

### Mcts_Volume_z_Cmo_52a8_15m.py (15m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 1.70, Max Drawdown = -19.12%
- **Monte Carlo Sharpe (Average)**: 1.15
- **Monte Carlo Max Drawdown (Average)**: -18.25% (5th percentile worst: -36.44%)
- **Robustness Profile**: The historical Sharpe lies at the **87.6th percentile** of the simulated distribution. The historical backtest represents a **highly realistic median expectation**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **36.6%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 1.05
- **Monte Carlo Max Drawdown (Average)**: -22.70% (5th percentile worst: -49.66%)
- **Pass Rate**: **28.6%**
- **Stress Impact**: Average drawdown worsened by **4.44%** compared to the normal scenario. This strategy has **strong structural resilience** to increased volatility regimes.

---

### Mcts_Rolling_rank_Atr_Rsi_40ed_15m.py (15m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 1.35, Max Drawdown = -12.21%
- **Monte Carlo Sharpe (Average)**: 1.00
- **Monte Carlo Max Drawdown (Average)**: -26.50% (5th percentile worst: -55.80%)
- **Robustness Profile**: The historical Sharpe lies at the **77.4th percentile** of the simulated distribution. The historical backtest represents a **highly realistic median expectation**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **27.0%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 0.85
- **Monte Carlo Max Drawdown (Average)**: -34.44% (5th percentile worst: -76.05%)
- **Pass Rate**: **16.0%**
- **Stress Impact**: Average drawdown worsened by **7.94%** compared to the normal scenario. This strategy has **strong structural resilience** to increased volatility regimes.

---

### Mcts_Rolling_rank_Tema_8587_15m.py (15m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 1.25, Max Drawdown = -26.88%
- **Monte Carlo Sharpe (Average)**: 1.03
- **Monte Carlo Max Drawdown (Average)**: -27.26% (5th percentile worst: -55.68%)
- **Robustness Profile**: The historical Sharpe lies at the **68.2th percentile** of the simulated distribution. The historical backtest represents a **highly realistic median expectation**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **28.0%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 1.02
- **Monte Carlo Max Drawdown (Average)**: -31.74% (5th percentile worst: -66.81%)
- **Pass Rate**: **27.6%**
- **Stress Impact**: Average drawdown worsened by **4.48%** compared to the normal scenario. This strategy has **strong structural resilience** to increased volatility regimes.

---

### Mcts_Natr_9fda_15m.py (15m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 1.18, Max Drawdown = -20.91%
- **Monte Carlo Sharpe (Average)**: 0.43
- **Monte Carlo Max Drawdown (Average)**: -53.92% (5th percentile worst: -125.20%)
- **Robustness Profile**: The historical Sharpe lies at the **96.0th percentile** of the simulated distribution. The strategy historical performance is an optimistic outlier, indicating **high risk of overfitting**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **2.6%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 0.34
- **Monte Carlo Max Drawdown (Average)**: -70.81% (5th percentile worst: -180.59%)
- **Pass Rate**: **1.6%**
- **Stress Impact**: Average drawdown worsened by **16.88%** compared to the normal scenario. This strategy is **highly vulnerable to regime shift** and extended periods of market stress.

---

### Mcts_Natr_a743_15m.py (15m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 1.18, Max Drawdown = -20.91%
- **Monte Carlo Sharpe (Average)**: 0.43
- **Monte Carlo Max Drawdown (Average)**: -53.92% (5th percentile worst: -125.20%)
- **Robustness Profile**: The historical Sharpe lies at the **96.0th percentile** of the simulated distribution. The strategy historical performance is an optimistic outlier, indicating **high risk of overfitting**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **2.6%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 0.34
- **Monte Carlo Max Drawdown (Average)**: -70.81% (5th percentile worst: -180.59%)
- **Pass Rate**: **1.6%**
- **Stress Impact**: Average drawdown worsened by **16.88%** compared to the normal scenario. This strategy is **highly vulnerable to regime shift** and extended periods of market stress.

---

### Mcts_Rolling_rank_Atr_7002_60m.py (60m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 1.14, Max Drawdown = -35.70%
- **Monte Carlo Sharpe (Average)**: 0.58
- **Monte Carlo Max Drawdown (Average)**: -44.83% (5th percentile worst: -104.77%)
- **Robustness Profile**: The historical Sharpe lies at the **90.2th percentile** of the simulated distribution. The strategy historical performance is an optimistic outlier, indicating **high risk of overfitting**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **5.6%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 0.66
- **Monte Carlo Max Drawdown (Average)**: -36.49% (5th percentile worst: -78.81%)
- **Pass Rate**: **6.0%**
- **Stress Impact**: Average drawdown worsened by **8.34%** compared to the normal scenario. This strategy has **strong structural resilience** to increased volatility regimes.

---

### Mcts_Rolling_rank_Atr_60f5_60m.py (60m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 1.08, Max Drawdown = -26.24%
- **Monte Carlo Sharpe (Average)**: 0.41
- **Monte Carlo Max Drawdown (Average)**: -27.62% (5th percentile worst: -53.05%)
- **Robustness Profile**: The historical Sharpe lies at the **91.8th percentile** of the simulated distribution. The strategy historical performance is an optimistic outlier, indicating **high risk of overfitting**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **3.0%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 0.52
- **Monte Carlo Max Drawdown (Average)**: -22.67% (5th percentile worst: -40.10%)
- **Pass Rate**: **6.6%**
- **Stress Impact**: Average drawdown worsened by **4.95%** compared to the normal scenario. This strategy has **strong structural resilience** to increased volatility regimes.

---

### Mcts_Rolling_zscore_Atr_daa4_60m.py (60m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 0.98, Max Drawdown = -29.74%
- **Monte Carlo Sharpe (Average)**: 0.51
- **Monte Carlo Max Drawdown (Average)**: -24.03% (5th percentile worst: -48.39%)
- **Robustness Profile**: The historical Sharpe lies at the **84.8th percentile** of the simulated distribution. The historical backtest represents a **highly realistic median expectation**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **5.4%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 0.59
- **Monte Carlo Max Drawdown (Average)**: -19.44% (5th percentile worst: -39.50%)
- **Pass Rate**: **6.2%**
- **Stress Impact**: Average drawdown worsened by **4.59%** compared to the normal scenario. This strategy has **strong structural resilience** to increased volatility regimes.

---

### Mcts_Rsi_Atr_114b_60m.py (60m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 0.97, Max Drawdown = -12.21%
- **Monte Carlo Sharpe (Average)**: 0.44
- **Monte Carlo Max Drawdown (Average)**: -17.80% (5th percentile worst: -38.32%)
- **Robustness Profile**: The historical Sharpe lies at the **86.8th percentile** of the simulated distribution. The historical backtest represents a **highly realistic median expectation**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **3.2%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 0.55
- **Monte Carlo Max Drawdown (Average)**: -14.50% (5th percentile worst: -29.28%)
- **Pass Rate**: **6.6%**
- **Stress Impact**: Average drawdown worsened by **3.30%** compared to the normal scenario. This strategy has **strong structural resilience** to increased volatility regimes.

---

### Mcts_Rsi_Atr_3540_60m.py (60m)

#### Normal Scenario
- **Historical Backtest**: Sharpe = 0.97, Max Drawdown = -29.62%
- **Monte Carlo Sharpe (Average)**: 0.48
- **Monte Carlo Max Drawdown (Average)**: -36.74% (5th percentile worst: -86.59%)
- **Robustness Profile**: The historical Sharpe lies at the **87.0th percentile** of the simulated distribution. The historical backtest represents a **highly realistic median expectation**.
- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **3.0%**

#### Stressed Scenario (1.5x Panic/Crash regime)
- **Monte Carlo Sharpe (Average)**: 0.54
- **Monte Carlo Max Drawdown (Average)**: -30.11% (5th percentile worst: -61.39%)
- **Pass Rate**: **5.4%**
- **Stress Impact**: Average drawdown worsened by **6.63%** compared to the normal scenario. This strategy has **strong structural resilience** to increased volatility regimes.

---

