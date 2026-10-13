# Plan: Alpha Farm Engine Refactoring Orchestration

## Objective
Execute complete refactoring of `alpha_farm` codebase to transition to pure Numpy time-series primitives (`AlphaPrimitives.py`), remove all legacy XNOQuant sandbox code, rename `XnoEngine.py` to `AlphaEngine.py`, update MCTS search space in `MCTSDimensions.py`, and achieve 100% test pass rate with benchmark performance proof.

## Milestone Plan

### Milestone 1: Erase Sandbox & Legacy Traces
- **Task**: Identify and remove all legacy files (`PlatformEmulator.py`, `SubmitStrategies.py`, `SandboxPrefixer.py`, `RestrictedSeries.py`). Audit the codebase for any remaining imports, calls, or references to these deleted modules and clean them up.
- **Verification**: Code search for `PlatformEmulator`, `SubmitStrategies`, `SandboxPrefixer`, `RestrictedSeries` returns 0 occurrences across active codebase.

### Milestone 2: Implement Numpy-based Primitives & Benchmark
- **Task**: Create `core_engine/AlphaPrimitives.py` implementing fast, vectorized Numpy time-series operators: `ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, `ts_argmin`. Write `benchmark_primitives.py` script to compare mathematical equivalence and speedup against standard Pandas `.rolling()` calls.
- **Verification**: Benchmark script runs cleanly, proving numerical equivalence within float precision tolerance (1e-6) and measurable speedup.

### Milestone 3: Refactor Engine to AlphaEngine
- **Task**: Rename `core_engine/XnoEngine.py` to `core_engine/AlphaEngine.py`. Remove `FeatureEngine` (TALib wrapper) and `OperatorEngine`. Retain and integrate `BacktestEngine`. Update all imports across the codebase (`main.py`, `test_pool.py`, `strategy_workflows`, `tests/`) to reference `AlphaEngine`.
- **Verification**: Import checks and unit tests for `AlphaEngine` pass without references to `FeatureEngine` or `OperatorEngine`.

### Milestone 4: Update MCTS Search Space
- **Task**: Update `strategy_workflows/MCTSDimensions.py` to remove traditional TA-Lib indicators (RSI, MACD, BBands, Candlesticks, etc.) and register the new primitive operators from `AlphaPrimitives.py`. Update `SemanticCompiler.py` or strategy generation logic if necessary to support new primitives.
- **Verification**: Search in `MCTSDimensions.py` returns 0 instances of traditional TA-Lib indicators or candlestick functions.

### Milestone 5: Test Suite Adaptation & Final Verification
- **Task**: Adapt test suite in `tests/` to account for `AlphaEngine` and `AlphaPrimitives`. Run full `pytest tests/` and verify 0 failures. Execute Forensic Auditor check to guarantee integrity, clean code, no hardcoding, and zero legacy traces.
- **Verification**: `pytest tests/` passes with 0 failures, Forensic Auditor issues CLEAN verdict, benchmark script passes.

## Subagent Execution Strategy
- For each milestone:
  1. **Explorer**: Investigate target files, identify dependencies, propose fix/implementation plan.
  2. **Worker**: Implement code changes, run verification scripts/tests.
  3. **Reviewer**: Inspect changes for bugs, regression, clean code principles, and interface contracts.
  4. **Challenger**: Empirically stress-test math accuracy, edge cases, NaN/inf handling, and performance.
  5. **Auditor**: Verify integrity, complete removal of legacy features, no cheating or hardcoding.
