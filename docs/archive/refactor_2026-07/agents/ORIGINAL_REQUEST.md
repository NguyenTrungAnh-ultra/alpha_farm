# Original User Request

## Initial Request — 2026-07-21T13:05:38Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Refactor the `alpha_farm` MCTS discovery engine to operate purely on primitive time-series operators (e.g., ts_rank, ts_corr, ts_max, ts_mean) via fast Numpy operations. Completely decouple the engine from the XNOQuant Sandbox limitations (remove RestrictedSeries, Playwright submitters, and TA-Lib indicators like MACD/RSI).

Working directory: f:/Projects/alpha_farm
Integrity mode: demo

## Requirements

### R1. Erase Sandbox & Legacy Traces
Delete all modules tied to the XNOQuant web competition: `PlatformEmulator.py`, `SubmitStrategies.py`, `SandboxPrefixer.py`, and the `RestrictedSeries` class. Ensure no code depends on them.

### R2. Refactor Engine to AlphaEngine
Rename `XnoEngine.py` to `AlphaEngine.py`. Rip out the `FeatureEngine` (TALib wrappers) and `OperatorEngine`. Retain the `BacktestEngine` logic (netting fees, margin calls, rollover) as it accurately simulates the VN30F futures market.

### R3. Implement Numpy-based Primitives
Create a new module (e.g., `AlphaPrimitives.py`) with highly optimized time-series operators using Numpy (`stride_tricks` or similar) to replace slow Pandas `.rolling().apply()` calls. Required primitives: `ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, `ts_argmin`.

### R4. Update MCTS Search Space
Update `MCTSDimensions.py` to wipe out traditional indicators (RSI, MACD, BBands, Candlesticks) and register the new primitive operators so the MCTS can discover novel mathematical combinations.

## Acceptance Criteria

### Verification & Accuracy
- [ ] A benchmark/verification script is provided that demonstrates the new primitive operators (like `ts_rank`, `ts_corr`) produce mathematically equivalent results to naive Pandas implementations, but execute significantly faster.
- [ ] Running `pytest tests/` returns 0 failures after modifying the existing test suite to adapt to the decoupled `AlphaEngine` architecture.
- [ ] No `RestrictedSeries` objects exist in the data flow; the MCTS and BacktestEngine operate entirely on `numpy.ndarray` or `pd.Series`.
- [ ] The `MCTSDimensions.py` registry contains 0 instances of traditional TA-Lib indicators or candlestick patterns.
