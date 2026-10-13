# Handoff Report: Explorer 3 — Legacy Sandbox Traces & RestrictedSeries Analysis

## 1. Observation
- **Legacy Files Identified for Removal**:
  - `core_engine/RestrictedSeries.py`: Custom wrapper around `pd.Series` (164 lines) designed to enforce web sandbox restrictions by intercepting method access via `__getattr__` (line 71), physical indexing via `__getitem__` (line 100), and overloading operators (`__add__`, `__sub__`, `__mul__`, `__gt__`, etc., lines 123-158).
  - `core_engine/PlatformEmulator.py`: Web emulator wrapper class `XNOPlatformEmulator` (189 lines) containing file loader and backtest runner.
  - `strategy_workflows/SubmitStrategies.py`: Playwright web submit automation script (817 lines).
  - `utilities/SandboxPrefixer.py`: Syntax & API prefix cleaner (387 lines) for XNO web sandbox syntax.
- **Code References to `RestrictedSeries` & Legacy Modules**:
  - `core_engine/BacktestEngine.py:196-197`: `if type(positions).__name__ == 'RestrictedSeries': positions = positions._data`.
  - `core_engine/XnoEngine.py:24`: `from .RestrictedSeries import RestrictedSeries`, used extensively in `FeatureEngine` (`_unwrap`, `_wrap`), `OperatorEngine` (`_unwrap`, `_wrap`), `DataProxy` (`pv_open = RestrictedSeries(df['Open'])`, lines 778-784), and `SimpleAlgorithm.set_positions` (line 820).
  - `strategy_workflows/HMMValidation.py:23,285,297,396`: Imports and uses `XNOPlatformEmulator`.
  - `main.py:9,92`: Imports `SubmitStrategies` in `cmd_submit`.
  - `refactor_imports.py:40-46,64-66,100-102`: Import mapping rules for `PlatformEmulator`, `RestrictedSeries`, `SubmitStrategies`, `SandboxPrefixer`.

## 2. Logic Chain
- **Step 1: Problem Definition**: Alpha Farm is being decoupled from the web competition sandbox into a standalone, pure NumPy/Pandas MCTS discovery engine (`AlphaPrimitives.py` & `AlphaEngine.py`). `RestrictedSeries` and web sandbox emulator components are legacy artifacts that create computational overhead and maintenance complexity.
- **Step 2: RestrictedSeries Overhead**: `RestrictedSeries` wraps `pd.Series` and overloads arithmetic/boolean operators. During MCTS strategy evaluation, every indicator calculation creates multiple wrapper instances, unwraps `_data`, executes Pandas ops, and re-wraps the result. Replacing `RestrictedSeries` with plain `pd.Series` or `np.ndarray` eliminates wrapper object creation and indirection.
- **Step 3: Compatibility Assessment for `BacktestEngine.py`**: `BacktestEngine.run()` accepts target position time-series (`positions`), applies `positions.shift(1).fillna(0.0)`, and performs bar-by-bar netting, margin call, and trade reconstruction. Plain `pd.Series` (or `np.ndarray`) natively supports `.shift(1)`, `.fillna(0.0)`, and NumPy vector indexing. Deleting the `RestrictedSeries` check in `BacktestEngine.py` preserves 100% of backtesting functionality.
- **Step 4: Phased Removal Plan**: Removing 4 target files (`RestrictedSeries.py`, `PlatformEmulator.py`, `SubmitStrategies.py`, `SandboxPrefixer.py`) and updating dependent modules (`BacktestEngine.py`, `XnoEngine.py`, `HMMValidation.py`, `main.py`, `refactor_imports.py`) cleanly eliminates all sandbox traces without breaking engine execution.

## 3. Caveats
- **Scope Limit**: This investigation is read-only. No source files outside the `.agents/` folder were modified.
- **Milestone Coupling**: Full renaming of `XnoEngine.py` to `AlphaEngine.py` and deletion of `FeatureEngine` / `OperatorEngine` are scheduled for Milestone 3. In Milestone 1, `FeatureEngine` and `OperatorEngine` in `XnoEngine.py` can be refactored to work with plain `pd.Series` once `RestrictedSeries.py` is removed.

## 4. Conclusion
- `RestrictedSeries` can be safely removed and replaced with standard `pd.Series` / `np.ndarray` without breaking `BacktestEngine`.
- The 4 legacy files (`RestrictedSeries.py`, `PlatformEmulator.py`, `SubmitStrategies.py`, `SandboxPrefixer.py`) are fully isolated and ready for deletion in Milestone 1.
- All code dependencies in `BacktestEngine.py`, `XnoEngine.py`, `HMMValidation.py`, `main.py`, and `refactor_imports.py` have been identified with exact line numbers for implementers.

## 5. Verification Method
- **Pytest Suite Execution**: Run `pytest tests/test_core_engine.py` using terminal tool to verify that `BacktestEngine` passes all unit tests (P&L calculations, margin call thresholding, trade reconstruction) when operating on plain `pd.Series`.
- **Grep Inspection**: Run project-wide `grep_search` for `RestrictedSeries`, `PlatformEmulator`, `SubmitStrategies`, `SandboxPrefixer` to confirm 0 remaining references in source code.
- **Invalidation Condition**: If `pytest tests/test_core_engine.py` fails or if any active module throws `ImportError` or `AttributeError` during execution.
