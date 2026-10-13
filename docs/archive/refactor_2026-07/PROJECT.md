# Project: Alpha Farm Engine Refactoring

## Architecture
Decoupled MCTS strategy discovery engine operating on pure Numpy time-series primitives (`AlphaPrimitives.py`) and standard Pandas/Numpy data structures.
Removed all legacy competition web sandbox mechanisms (`PlatformEmulator`, `SubmitStrategies`, `SandboxPrefixer`, `RestrictedSeries`, TA-Lib dependencies).
Core components:
- `core_engine/AlphaEngine.py`: Renamed from `XnoEngine.py`, stripped of `FeatureEngine` and `OperatorEngine`, retaining `BacktestEngine`.
- `core_engine/AlphaPrimitives.py`: High-performance time-series operations using vectorized Numpy (`ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, `ts_argmin`).
- `strategy_workflows/MCTSDimensions.py`: Updated MCTS primitive dimension space (0 TA-Lib indicators or candlesticks).
- Verification & Test suite: Benchmark script for primitive speed & accuracy, updated pytest test suite.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Erase Sandbox & Legacy Traces | Delete PlatformEmulator.py, SubmitStrategies.py, SandboxPrefixer.py, RestrictedSeries.py; remove all code/import references | none | DONE |
| 2 | Implement AlphaPrimitives & Benchmark | Create core_engine/AlphaPrimitives.py with fast Numpy operators + benchmark_primitives.py verification script | M1 | DONE |
| 3 | Refactor Engine to AlphaEngine | Rename XnoEngine.py -> AlphaEngine.py, remove FeatureEngine & OperatorEngine, retain BacktestEngine | M1, M2 | DONE |
| 4 | Update MCTSDimensions Search Space | Wipe traditional TA-Lib indicators/candlesticks from MCTSDimensions.py, register new primitives | M2, M3 | IN_PROGRESS |
| 5 | Test Suite Adaptation & E2E Validation | Update pytest suite in tests/, run benchmark & pytest, verify 0 failures and 0 RestrictedSeries/TA-Lib references | M1-M4 | PLANNED |

## Code Layout
- `core_engine/AlphaEngine.py`: Core backtest engine wrapper.
- `core_engine/AlphaPrimitives.py`: Vectorized Numpy time-series primitives.
- `core_engine/BacktestEngine.py`: Futures backtest logic (margin, fees, rollover).
- `core_engine/CalculateMetrics.py`, `GenerateReport.py`: Metrics and reporting.
- `strategy_workflows/MCTSDimensions.py`: MCTS dimension and operator space definitions.
- `strategy_workflows/MCTSEngine.py`, `SemanticCompiler.py`, `GenerateStrategies.py`: Strategy generation & evaluation.
- `tests/`: Pytest test suite for core engine and workflow validation.
- `benchmark_primitives.py`: Benchmark script comparing AlphaPrimitives against Pandas baseline.
