# Systematic Alpha Validation Report (149 Alphas)

This report presents the validation of all 149 pushed alphas in `results/pushed/` using the HMM-guided Monte Carlo validation rules.

## Validation Rules Summary

A strategy is accepted (**YES**) if it satisfies:
1. **(Rule 1 AND Rule 2)** OR **Rule 3**

Where:
- **Rule 1 (Overfitting Filter)**: `Historical Sharpe Percentile <= 85%` (The historical backtest must not be an extreme outlier/lucky path).
- **Rule 2 (Edge Retainment)**: `MC Sharpe mean (Normal) >= 0.5 * Historical Sharpe` (The strategy must retain at least 50% of its Sharpe on synthetic paths).
- **Rule 3 (Stress Resilience Bonus)**: `MC Sharpe mean (Stressed) >= MC Sharpe mean (Normal)` (The strategy structurally benefits from or remains stable under increased volatility and crash regimes).

## Executive Metrics

- **Total Evaluated Alphas**: 149
- **Passed (YES)**: 39 (26.2%)
- **Failed (NO)**: 110 (73.8%)

### Pass Rate by Timeframe

| Timeframe | Evaluated | Passed (YES) | Failed (NO) | Pass Rate (%) |
|---|---|---|---|---|
| 10m | 20 | 3 | 17 | 15.0% |
| 15m | 24 | 15 | 9 | 62.5% |
| 1m | 31 | 0 | 31 | 0.0% |
| 30m | 25 | 6 | 19 | 24.0% |
| 3m | 14 | 0 | 14 | 0.0% |
| 5m | 19 | 0 | 19 | 0.0% |
| 60m | 16 | 15 | 1 | 93.8% |

## Passed Alphas (YES)

| Strategy | TF | Hist Sharpe | MC Sharpe | Stressed Sharpe | Hist Percentile | Reason |
|---|---|---|---|---|---|---|
| Mcts_Rsi_f093_10m.py | 10m | 2.11 | 1.55 | 1.66 | 91.3% | Stress Resilient (Rule 3) |
| Mcts_Rsi_2a59_10m.py | 10m | 1.95 | 1.52 | 1.62 | 87.3% | Stress Resilient (Rule 3) |
| Mcts_Rolling_rank_Wma_885e_10m.py | 10m | 1.49 | 1.11 | 1.17 | 83.3% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rolling_rank_Atr_Rsi_40ed_15m.py | 15m | 1.35 | 1.01 | 1.13 | 75.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rolling_rank_Tema_8587_15m.py | 15m | 1.25 | 0.97 | 1.14 | 67.5% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Natr_9fda_15m.py | 15m | 1.18 | 0.43 | 0.57 | 93.5% | Stress Resilient (Rule 3) |
| Mcts_Natr_a743_15m.py | 15m | 1.18 | 0.43 | 0.57 | 93.5% | Stress Resilient (Rule 3) |
| Mcts_Natr_6d33_15m.py | 15m | 1.03 | 0.44 | 0.56 | 89.5% | Stress Resilient (Rule 3) |
| Mcts_Natr_5899_15m.py | 15m | 1.03 | 0.39 | 0.50 | 89.5% | Stress Resilient (Rule 3) |
| Mcts_Zscore_Rsi_Ema_ac6d_15m.py | 15m | 0.99 | 0.58 | 0.64 | 81.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Atr_6129_15m.py | 15m | 0.96 | 0.44 | 0.51 | 88.0% | Stress Resilient (Rule 3) |
| Mcts_Wma_Atr_f0a0_15m.py | 15m | 0.94 | 0.35 | 0.44 | 90.0% | Stress Resilient (Rule 3) |
| Mcts_Ema_Atr_c531_15m.py | 15m | 0.91 | 0.38 | 0.49 | 88.5% | Stress Resilient (Rule 3) |
| Mcts_Dema_Atr_ddba_15m.py | 15m | 0.90 | 0.40 | 0.50 | 86.0% | Stress Resilient (Rule 3) |
| Mcts_Atr_8ce4_15m.py | 15m | 0.90 | 0.38 | 0.49 | 86.5% | Stress Resilient (Rule 3) |
| Mcts_Atr_3eb1_15m.py | 15m | 0.89 | 0.41 | 0.48 | 88.0% | Stress Resilient (Rule 3) |
| Mcts_Dema_Atr_0cd5_15m.py | 15m | 0.87 | 0.42 | 0.47 | 85.0% | Stress Resilient (Rule 3) |
| Mcts_Dema_Atr_a325_15m.py | 15m | 0.76 | 0.44 | 0.53 | 77.5% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Zscore_Rsi_Ema_fed3_30m.py | 30m | 2.36 | 1.30 | 1.90 | 90.4% | Stress Resilient (Rule 3) |
| Mcts_Zscore_Macd_9176_30m.py | 30m | 1.86 | 0.49 | 0.58 | 99.6% | Stress Resilient (Rule 3) |
| Mcts_Tema_Atr_d691_30m.py | 30m | 1.51 | 0.42 | 0.72 | 96.4% | Stress Resilient (Rule 3) |
| Mcts_Cmo_Ema_Atr_ef22_30m.py | 30m | 1.05 | 0.37 | 0.54 | 88.0% | Stress Resilient (Rule 3) |
| Mcts_Rsi_Wma_Atr_8f9b_30m.py | 30m | 0.95 | 0.33 | 0.49 | 86.4% | Stress Resilient (Rule 3) |
| Mcts_Natr_66ef_30m.py | 30m | 0.81 | 0.49 | 0.72 | 70.4% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rolling_rank_Atr_7002_60m.py | 60m | 1.14 | 0.54 | 0.71 | 91.0% | Stress Resilient (Rule 3) |
| Mcts_Rolling_rank_Atr_60f5_60m.py | 60m | 1.08 | 0.40 | 0.60 | 89.0% | Stress Resilient (Rule 3) |
| Mcts_Rolling_zscore_Atr_daa4_60m.py | 60m | 0.98 | 0.50 | 0.72 | 82.3% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rsi_Atr_114b_60m.py | 60m | 0.97 | 0.47 | 0.67 | 82.0% | Stress Resilient (Rule 3) |
| Mcts_Rsi_Atr_3540_60m.py | 60m | 0.97 | 0.52 | 0.64 | 82.7% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rolling_zscore_Atr_c14e_60m.py | 60m | 0.95 | 0.45 | 0.67 | 84.0% | Stress Resilient (Rule 3) |
| Mcts_Rolling_rank_Dema_Atr_9a33_60m.py | 60m | 0.91 | 0.54 | 0.71 | 80.3% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rsi_Atr_e3f0_60m.py | 60m | 0.90 | 0.42 | 0.59 | 85.7% | Stress Resilient (Rule 3) |
| Mcts_Rolling_zscore_Atr_74b3_60m.py | 60m | 0.80 | 0.57 | 0.76 | 69.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rolling_zscore_Atr_6c0e_60m.py | 60m | 0.67 | 0.44 | 0.63 | 70.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rolling_zscore_Atr_8c2b_60m.py | 60m | 0.67 | 0.44 | 0.63 | 70.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Cmo_Atr_3908_60m.py | 60m | 0.62 | 0.49 | 0.58 | 61.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rolling_zscore_Atr_77a8_60m.py | 60m | 0.52 | 0.47 | 0.67 | 52.3% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rsi_Atr_2df7_60m.py | 60m | 0.48 | 0.42 | 0.57 | 54.7% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |
| Mcts_Rolling_zscore_Dema_Atr_4fd4_60m.py | 60m | 0.45 | 0.48 | 0.66 | 49.7% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3) |

## Sample Failed Alphas (NO - Top 20 by Hist Sharpe)

| Strategy | TF | Hist Sharpe | MC Sharpe | Stressed Sharpe | Hist Percentile | Failed Rules |
|---|---|---|---|---|---|---|
| Mcts_Cmo_Wma_Tema_3f40_30m.py | 30m | 1.73 | 0.19 | 0.46 | 99.6% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Volume_z_Cmo_52a8_15m.py | 15m | 1.70 | 1.16 | 1.13 | 87.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3 (Stress Vulnerability) |
| Mcts_Cmo_Atr_c581_30m.py | 30m | 1.69 | 0.14 | 0.34 | 100.0% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Tema_Atr_b046_30m.py | 30m | 1.56 | 0.30 | 0.65 | 97.2% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Atr_9287_30m.py | 30m | 1.55 | 0.26 | 0.58 | 98.4% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Rsi_Atr_5550_30m.py | 30m | 1.45 | 0.05 | 0.22 | 97.6% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Cmo_Atr_e2a2_30m.py | 30m | 1.40 | 0.18 | 0.42 | 97.2% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Rsi_Atr_f01a_30m.py | 30m | 1.40 | 0.18 | 0.42 | 97.2% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Rolling_rank_Wma_Atr_2dc3_30m.py | 30m | 1.40 | 0.07 | 0.28 | 97.6% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Rsi_Atr_74c0_30m.py | 30m | 1.37 | 0.17 | 0.36 | 97.6% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Tema_Atr_9f83_30m.py | 30m | 1.36 | 0.16 | 0.48 | 94.0% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Rolling_rank_Wma_Atr_be2b_30m.py | 30m | 1.31 | 0.03 | 0.28 | 96.0% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Roc_Sma_Atr_fd02_3m.py | 3m | 1.30 | 0.03 | 0.09 | 100.0% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Cmo_Ema_Atr_3811_30m.py | 30m | 1.21 | 0.05 | 0.29 | 95.6% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Rsi_Wma_Ema_81c6_30m.py | 30m | 1.16 | 0.25 | 0.40 | 93.6% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Wma_Dema_Atr_5ff2_15m.py | 15m | 1.08 | 0.21 | 0.33 | 94.0% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Ema_Sma_4f71_10m.py | 10m | 1.08 | 0.06 | 0.06 | 99.3% | Rule 1&2 (Overfit/Edge Loss), Rule 3 (Stress Vulnerability) |
| Mcts_Roc_Tema_Atr_2424_30m.py | 30m | 1.07 | 0.24 | 0.42 | 91.2% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Rsi_Atr_c458_30m.py | 30m | 1.05 | 0.15 | 0.29 | 92.4% | Rule 1&2 (Overfit/Edge Loss) |
| Mcts_Atr_361e_30m.py | 30m | 1.05 | 0.23 | 0.57 | 91.6% | Rule 1&2 (Overfit/Edge Loss) |
