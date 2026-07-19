# Systematic Alpha Validation Report (149 Alphas)

This report presents the validation of all 149 pushed alphas in `results/pushed/` using the HMM-guided Monte Carlo validation rules.

## Validation Rules Summary

A strategy is accepted (**YES**) if it satisfies:
1. **(Rule 1 AND Rule 2)** OR **(Rule 3 AND Rule 4)**

Where:
- **Rule 1 (Overfitting Filter)**: `Historical Sharpe Percentile <= 85%` (The historical backtest must not be an extreme outlier/lucky path).
- **Rule 2 (Edge Retainment)**: `MC Sharpe mean (Normal) >= 0.5 * Historical Sharpe` (The strategy must retain at least 50% of its Sharpe on synthetic paths).
- **Rule 3 (Stress Resilience Bonus)**: `MC Sharpe mean (Stressed) >= MC Sharpe mean (Normal)` (The strategy structurally benefits from or remains stable under increased volatility and crash regimes).
- **Rule 4 (Minimum Edge Threshold)**: `MC Sharpe mean (Normal) >= 0.3` (The strategy must demonstrate a minimum viable performance in the simulated world. This filters out overfitted near-zero noise strategies passing Rule 3 by chance).

## Executive Metrics

- **Total Evaluated Alphas**: 149
- **Passed (YES)**: 34 (22.8%)
- **Failed (NO)**: 115 (77.2%)

### Pass Rate by Timeframe

| Timeframe | Evaluated | Passed (YES) | Failed (NO) | Pass Rate (%) |
|---|---|---|---|---|
| 10m | 20 | 3 | 17 | 15.0% |
| 15m | 24 | 4 | 20 | 16.7% |
| 1m | 31 | 0 | 31 | 0.0% |
| 30m | 25 | 12 | 13 | 48.0% |
| 3m | 14 | 0 | 14 | 0.0% |
| 5m | 19 | 0 | 19 | 0.0% |
| 60m | 16 | 15 | 1 | 93.8% |

## Passed Alphas (YES)

| Strategy | TF | Hist Sharpe | MC Sharpe | Stressed Sharpe | Hist Percentile | Reason |
|---|---|---|---|---|---|---|
| Mcts_Rsi_2a59_10m.py | 10m | 1.95 | 1.49 | 1.31 | 83.0% | Robust (Rule 1 & 2) |
| Mcts_Rolling_rank_Wma_885e_10m.py | 10m | 1.49 | 1.15 | 0.89 | 81.0% | Robust (Rule 1 & 2) |
| Mcts_Rsi_9f6c_10m.py | 10m | 1.03 | 0.64 | 0.36 | 81.0% | Robust (Rule 1 & 2) |
| Mcts_Rolling_rank_Atr_Rsi_40ed_15m.py | 15m | 1.35 | 1.02 | 0.81 | 75.5% | Robust (Rule 1 & 2) |
| Mcts_Rolling_rank_Tema_8587_15m.py | 15m | 1.25 | 1.04 | 0.98 | 65.5% | Robust (Rule 1 & 2) |
| Mcts_Zscore_Rsi_Ema_ac6d_15m.py | 15m | 0.99 | 0.62 | 0.57 | 79.5% | Robust (Rule 1 & 2) |
| Mcts_Dema_Atr_a325_15m.py | 15m | 0.76 | 0.40 | 0.34 | 82.0% | Robust (Rule 1 & 2) |
| Mcts_Zscore_Rsi_Ema_fed3_30m.py | 30m | 2.36 | 1.33 | 1.52 | 89.0% | Stress Resilient (Rule 3 & 4) |
| Mcts_Cmo_Wma_Tema_3f40_30m.py | 30m | 1.73 | 0.33 | 0.44 | 98.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Tema_Atr_b046_30m.py | 30m | 1.56 | 0.43 | 0.60 | 93.0% | Stress Resilient (Rule 3 & 4) |
| Mcts_Atr_9287_30m.py | 30m | 1.55 | 0.36 | 0.49 | 95.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Tema_Atr_d691_30m.py | 30m | 1.51 | 0.53 | 0.65 | 91.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rsi_Wma_Ema_81c6_30m.py | 30m | 1.16 | 0.38 | 0.47 | 89.0% | Stress Resilient (Rule 3 & 4) |
| Mcts_Cmo_Ema_Atr_ef22_30m.py | 30m | 1.05 | 0.45 | 0.59 | 85.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Atr_361e_30m.py | 30m | 1.05 | 0.34 | 0.48 | 87.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rsi_Wma_Atr_8f9b_30m.py | 30m | 0.95 | 0.44 | 0.55 | 82.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Roc_Sma_Atr_4a36_30m.py | 30m | 0.95 | 0.33 | 0.39 | 81.0% | Stress Resilient (Rule 3 & 4) |
| Mcts_Natr_66ef_30m.py | 30m | 0.81 | 0.62 | 0.74 | 60.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |
| Mcts_Roc_Wma_Ema_97aa_30m.py | 30m | 0.75 | 0.39 | 0.39 | 72.0% | Robust (Rule 1 & 2) |
| Mcts_Rolling_rank_Atr_7002_60m.py | 60m | 1.14 | 0.53 | 0.67 | 90.0% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_rank_Atr_60f5_60m.py | 60m | 1.08 | 0.35 | 0.57 | 92.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_zscore_Atr_daa4_60m.py | 60m | 0.98 | 0.46 | 0.61 | 85.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rsi_Atr_114b_60m.py | 60m | 0.97 | 0.40 | 0.58 | 88.0% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rsi_Atr_3540_60m.py | 60m | 0.97 | 0.47 | 0.58 | 85.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_zscore_Atr_c14e_60m.py | 60m | 0.95 | 0.42 | 0.55 | 87.0% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_rank_Dema_Atr_9a33_60m.py | 60m | 0.91 | 0.55 | 0.67 | 81.5% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |
| Mcts_Rsi_Atr_e3f0_60m.py | 60m | 0.90 | 0.37 | 0.50 | 90.5% | Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_zscore_Atr_74b3_60m.py | 60m | 0.80 | 0.52 | 0.65 | 75.5% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_zscore_Atr_6c0e_60m.py | 60m | 0.67 | 0.40 | 0.53 | 73.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_zscore_Atr_8c2b_60m.py | 60m | 0.67 | 0.40 | 0.53 | 73.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |
| Mcts_Cmo_Atr_3908_60m.py | 60m | 0.62 | 0.35 | 0.47 | 76.5% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_zscore_Atr_77a8_60m.py | 60m | 0.52 | 0.45 | 0.60 | 57.5% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |
| Mcts_Rsi_Atr_2df7_60m.py | 60m | 0.48 | 0.30 | 0.47 | 67.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |
| Mcts_Rolling_zscore_Dema_Atr_4fd4_60m.py | 60m | 0.45 | 0.50 | 0.65 | 47.0% | Robust (Rule 1 & 2) + Stress Resilient (Rule 3 & 4) |

## Sample Failed Alphas (NO - Top 20 by Hist Sharpe)

| Strategy | TF | Hist Sharpe | MC Sharpe | Stressed Sharpe | Hist Percentile | Failed Rules |
|---|---|---|---|---|---|---|
| Mcts_Rsi_f093_10m.py | 10m | 2.11 | 1.53 | 1.33 | 89.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Zscore_Macd_9176_30m.py | 30m | 1.86 | 0.56 | 0.54 | 97.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Volume_z_Cmo_52a8_15m.py | 15m | 1.70 | 1.17 | 1.09 | 86.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Cmo_Atr_c581_30m.py | 30m | 1.69 | 0.24 | 0.36 | 99.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Rsi_Atr_5550_30m.py | 30m | 1.45 | 0.13 | 0.25 | 97.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Cmo_Atr_e2a2_30m.py | 30m | 1.40 | 0.30 | 0.37 | 95.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Rsi_Atr_f01a_30m.py | 30m | 1.40 | 0.30 | 0.37 | 95.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Rolling_rank_Wma_Atr_2dc3_30m.py | 30m | 1.40 | 0.20 | 0.34 | 97.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Rsi_Atr_74c0_30m.py | 30m | 1.37 | 0.26 | 0.35 | 95.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Tema_Atr_9f83_30m.py | 30m | 1.36 | 0.27 | 0.38 | 95.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Rolling_rank_Wma_Atr_be2b_30m.py | 30m | 1.31 | 0.23 | 0.36 | 93.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Roc_Sma_Atr_fd02_3m.py | 3m | 1.30 | 0.05 | 0.06 | 100.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Cmo_Ema_Atr_3811_30m.py | 30m | 1.21 | 0.19 | 0.35 | 93.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Natr_9fda_15m.py | 15m | 1.18 | 0.43 | 0.32 | 96.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Natr_a743_15m.py | 15m | 1.18 | 0.43 | 0.32 | 96.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Wma_Dema_Atr_5ff2_15m.py | 15m | 1.08 | 0.12 | 0.02 | 97.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Ema_Sma_4f71_10m.py | 10m | 1.08 | 0.11 | 0.06 | 99.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Roc_Tema_Atr_2424_30m.py | 30m | 1.07 | 0.29 | 0.37 | 87.5% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Rsi_Atr_c458_30m.py | 30m | 1.05 | 0.21 | 0.35 | 91.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
| Mcts_Natr_6d33_15m.py | 15m | 1.03 | 0.45 | 0.31 | 92.0% | Rule 1&2 (Overfit/Edge Loss), Rule 3&4 (Stress Vulnerability/No Edge) |
