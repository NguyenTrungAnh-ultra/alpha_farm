# Regime Tagging Feasibility Test Report

This report summarizes the feasibility test of using Hidden Markov Models (HMM) for tagging market regimes on VN30F futures data.

## Timeframe: 15m | States: 2

### State Statistics
| State | Count | Percentage | Mean Log Return | Std Log Return | Win Rate (%) | Mean Volatility Feature |
|---|---|---|---|---|---|---|
| 0 | 17197 | 81.18% | 0.000077 | 0.001980 | 48.43% | 0.002048 |
| 1 | 3988 | 18.82% | -0.000225 | 0.007029 | 47.62% | 0.006029 |

### Transition Probability Matrix
```
  0.9899  0.0101
  0.0427  0.9573
```

### State Parameter Estimates
- **Means (Log Return, Volatility Feature)**:
  - State 0: Return Mean = 0.000075, Vol Mean = 0.002044
  - State 1: Return Mean = -0.000210, Vol Mean = 0.005981
- **Covariances (Diagonal Elements)**:
  - State 0: Return Var = 0.00000446, Vol Var = 0.00000121
  - State 1: Return Var = 0.00005130, Vol Var = 0.00001136

---

## Timeframe: 15m | States: 3

### State Statistics
| State | Count | Percentage | Mean Log Return | Std Log Return | Win Rate (%) | Mean Volatility Feature |
|---|---|---|---|---|---|---|
| 0 | 15830 | 74.72% | 0.000071 | 0.001908 | 48.31% | 0.001911 |
| 1 | 536 | 2.53% | -0.000559 | 0.014173 | 47.95% | 0.011086 |
| 2 | 4819 | 22.75% | -0.000080 | 0.004540 | 48.21% | 0.004789 |

### Transition Probability Matrix
```
  0.9915  0.0033  0.0052
  0.0318  0.8401  0.1282
  0.0241  0.0077  0.9682
```

### State Parameter Estimates
- **Means (Log Return, Volatility Feature)**:
  - State 0: Return Mean = 0.000073, Vol Mean = 0.001911
  - State 1: Return Mean = -0.000654, Vol Mean = 0.010757
  - State 2: Return Mean = -0.000075, Vol Mean = 0.004787
- **Covariances (Diagonal Elements)**:
  - State 0: Return Var = 0.00000425, Vol Var = 0.00000107
  - State 1: Return Var = 0.00021565, Vol Var = 0.00004687
  - State 2: Return Var = 0.00002235, Vol Var = 0.00000378

---

## Timeframe: 60m | States: 2

### State Statistics
| State | Count | Percentage | Mean Log Return | Std Log Return | Win Rate (%) | Mean Volatility Feature |
|---|---|---|---|---|---|---|
| 0 | 4720 | 77.01% | 0.000219 | 0.004052 | 51.59% | 0.003968 |
| 1 | 1409 | 22.99% | -0.000399 | 0.011209 | 50.04% | 0.010486 |

### Transition Probability Matrix
```
  0.9948  0.0052
  0.0180  0.9820
```

### State Parameter Estimates
- **Means (Log Return, Volatility Feature)**:
  - State 0: Return Mean = 0.000217, Vol Mean = 0.003970
  - State 1: Return Mean = -0.000394, Vol Mean = 0.010473
- **Covariances (Diagonal Elements)**:
  - State 0: Return Var = 0.00001855, Vol Var = 0.00000362
  - State 1: Return Var = 0.00013248, Vol Var = 0.00001994

---

## Timeframe: 60m | States: 3

### State Statistics
| State | Count | Percentage | Mean Log Return | Std Log Return | Win Rate (%) | Mean Volatility Feature |
|---|---|---|---|---|---|---|
| 0 | 2346 | 38.28% | 0.000145 | 0.005083 | 50.00% | 0.004058 |
| 1 | 2486 | 40.56% | 0.000276 | 0.002968 | 53.06% | 0.004036 |
| 2 | 1297 | 21.16% | -0.000429 | 0.011516 | 49.96% | 0.010755 |

### Transition Probability Matrix
```
  0.0003  0.9862  0.0134
  0.6502  0.3496  0.0002
  0.0082  0.0143  0.9775
```

### State Parameter Estimates
- **Means (Log Return, Volatility Feature)**:
  - State 0: Return Mean = 0.000189, Vol Mean = 0.004151
  - State 1: Return Mean = 0.000229, Vol Mean = 0.004061
  - State 2: Return Mean = -0.000470, Vol Mean = 0.010958
- **Covariances (Diagonal Elements)**:
  - State 0: Return Var = 0.00003207, Vol Var = 0.00000707
  - State 1: Return Var = 0.00001449, Vol Var = 0.00000521
  - State 2: Return Var = 0.00014643, Vol Var = 0.00002113

---

