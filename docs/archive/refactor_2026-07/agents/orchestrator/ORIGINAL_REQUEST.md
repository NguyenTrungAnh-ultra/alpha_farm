# Original User Request

## Initial Request — 2026-07-21T13:06:00Z

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

## Resumption Request — 2026-07-21T15:00:28Z

You are the PROJECT ORCHESTRATOR for the alpha_farm refactoring project (resuming after temporary pause).

Working directory: f:/Projects/alpha_farm
Your working directory: f:/Projects/alpha_farm/.agents/orchestrator

Current State:
- Read f:/Projects/alpha_farm/.agents/orchestrator/plan.md and progress.md.
- Milestone 1 is COMPLETE & AUDITED CLEAN.
- Milestone 2 worker implementation (`core_engine/AlphaPrimitives.py`, `benchmark_primitives.py`, `tests/test_alpha_primitives.py`) is complete.

Tasks:
1. Finish Milestone 2 verification/auditing and mark M2 complete.
2. Proceed to Milestone 3: Refactor Engine to `AlphaEngine.py` (rename `core_engine/XnoEngine.py` to `AlphaEngine.py`, remove `FeatureEngine` and `OperatorEngine`, retain `BacktestEngine`, update all codebase imports).
3. Proceed to Milestone 4: Update MCTS search space in `strategy_workflows/MCTSDimensions.py` (remove TA-Lib indicators and candlesticks, register new primitives).
4. Proceed to Milestone 5: Adapt test suite in `tests/`, run `pytest tests/`, execute benchmark script, run Forensic Auditor, and confirm 100% completion.
5. Send final project completion report when all acceptance criteria are met.

## Resumption Request — 2026-07-21T15:03:39Z

Resume work at f:\Projects\alpha_farm\.agents\orchestrator.
Read handoff.md, BRIEFING.md, ORIGINAL_REQUEST.md, plan.md, and progress.md for current state.
Your parent is fc113850-2338-45a2-a036-6b552409db1c — use this ID for all escalation and status reporting (send_message).

Current Project State:
- Milestone 1 (Erase Sandbox & Legacy Traces): DONE & AUDITED CLEAN.
- Milestone 2 (Implement AlphaPrimitives & Benchmark): DONE & AUDITED CLEAN.
- Milestone 3 (Refactor Engine to AlphaEngine): IN_PROGRESS. Proceed immediately with Milestone 3 execution (Explorer -> Worker -> Reviewer -> Challenger -> Auditor).
- Milestone 4 (Update MCTSDimensions Search Space): PLANNED.
- Milestone 5 (Test Suite Adaptation & Final Verification): PLANNED.

Start your heartbeat cron timer, dispatch M3 Explorers & Worker, and drive the project through M3, M4, and M5 to full completion!
