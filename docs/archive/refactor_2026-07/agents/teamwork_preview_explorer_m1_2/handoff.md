# Handoff Report: Audit of Sandbox & Legacy Traces Eradication (Milestone 1)

**Agent**: Explorer 2 (`teamwork_preview_explorer_m1_2`)  
**Working Directory**: `f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m1_2`  
**Date**: 2026-07-21  

---

## 1. Observation

Direct observations from codebase audit and file inspections:

1. **Legacy Files to be Deleted**:
   - `core_engine/PlatformEmulator.py`
   - `strategy_workflows/SubmitStrategies.py`
   - `utilities/SandboxPrefixer.py`
   - `core_engine/RestrictedSeries.py`

2. **Downstream References in Active Codebase**:
   - `strategy_workflows/HMMValidation.py:23`: `from core_engine.PlatformEmulator import XNOPlatformEmulator`
   - `strategy_workflows/HMMValidation.py:285`: `emulator = XNOPlatformEmulator()`
   - `strategy_workflows/HMMValidation.py:297`: `res = emulator.engine.run(strategy, sim_df)`
   - `strategy_workflows/HMMValidation.py:396`: `res = emulator.engine.run(strategy, sim_df)`
   - `main.py:92`: `from strategy_workflows.SubmitStrategies import run_auto_submit`
   - `main.py:79-116`: `cmd_submit(args)` function block
   - `main.py:130`: `cmd_submit(args)` call inside `cmd_full(args)`
   - `main.py:268, 336, 370`: `submit` subcommand choices in interactive menu, argparse subparsers, and execution router
   - `strategy_workflows/RunMCTS.py:177`: `logging.getLogger("core_engine.RestrictedSeries").setLevel(logging.CRITICAL)`
   - `core_engine/BacktestEngine.py:195-196`: `if type(positions).__name__ == 'RestrictedSeries': positions = positions._data`
   - `refactor_imports.py:40-46, 64-66, 100-102`: Regex replacement pairs for legacy import paths

3. **Test Suite Audit (`tests/`)**:
   - `tests/conftest.py`: 0 references to legacy modules.
   - `tests/test_core_engine.py`: 0 references to legacy modules. Uses `XNOBacktestEngine`.
   - `tests/test_hardware_concurrency.py`: 0 direct references to legacy modules, but imports `strategy_workflows.RunMCTS` and `strategy_workflows.HMMValidation`.
   - `tests/test_hmm_validation.py`: 0 direct references to legacy modules, but imports functions from `strategy_workflows.HMMValidation`.
   - `tests/test_mcts_engine.py`: 0 references to legacy modules.
   - `tests/test_semantic_compiler.py`: 0 references to legacy modules.

---

## 2. Logic Chain

1. **Observation 1 & 2** identify all explicit occurrences of `PlatformEmulator`, `SubmitStrategies`, `SandboxPrefixer`, and `RestrictedSeries` in the repository.
2. **Observation 3** confirms that no test inside `tests/` directly imports any of the 4 legacy files.
3. Therefore, deleting `PlatformEmulator.py`, `SubmitStrategies.py`, `SandboxPrefixer.py`, and `RestrictedSeries.py` will not break any unit logic inside the `tests/` directory itself.
4. However, because `tests/test_hmm_validation.py` and `tests/test_hardware_concurrency.py` import `strategy_workflows.HMMValidation`, deleting `PlatformEmulator.py` without updating `HMMValidation.py:23` will trigger a `ModuleNotFoundError` / `ImportError` during pytest collection.
5. In `HMMValidation.py`, `XNOPlatformEmulator` is used strictly as a wrapper to access `emulator.engine`, which is `XNOBacktestEngine`. Replacing `XNOPlatformEmulator` with direct `XNOBacktestEngine` instantiation removes the dependency on `PlatformEmulator.py` completely while preserving full HMM validation functionality.
6. In `main.py`, removing `cmd_submit` and the `submit` subcommand removes all dependencies on `SubmitStrategies.py`.
7. In `RunMCTS.py`, removing line 177 (`logging.getLogger("core_engine.RestrictedSeries")...`) eliminates the logger reference to `RestrictedSeries`.
8. In `BacktestEngine.py`, removing lines 195-196 cleans up the dead legacy type check.
9. Upon completing these 4 code modifications alongside deleting the 4 legacy files, all downstream imports and fixtures will be clean, and `pytest` will collect and execute all test files without error.

---

## 3. Caveats

- **`core_engine/XnoEngine.py`**: Contains multiple references to `RestrictedSeries` (lines 24, 114, 115, 178, 184, 434, 485, 488, 506). `XnoEngine.py` is scheduled for refactoring into `AlphaEngine.py` under Milestone 3. For Milestone 1 completion, removing `RestrictedSeries.py` means any code path in `XnoEngine.py` calling `RestrictedSeries` would fail if executed; however, `XnoEngine.py` itself will be updated in M3.

---

## 4. Conclusion

1. **Impacted Tests**: No test in `tests/` directly imports the 4 legacy modules. Tests will only fail if `HMMValidation.py:23` is not updated when `PlatformEmulator.py` is deleted.
2. **Downstream Files Requiring Edits**:
   - `strategy_workflows/HMMValidation.py` (lines 23, 285, 297, 396)
   - `main.py` (lines 9, 79-116, 130, 268, 336, 370)
   - `strategy_workflows/RunMCTS.py` (line 177)
   - `core_engine/BacktestEngine.py` (lines 195-196)
   - `refactor_imports.py` (lines 40-46, 64-66, 100-102)
   - `README.md` & `docs/ARCH.md`
3. **Actionability**: Implementers can safely delete the 4 target legacy files and apply the specified line edits in `HMMValidation.py`, `main.py`, `RunMCTS.py`, and `BacktestEngine.py`.

---

## 5. Verification Method

1. **Codebase Grep Search**:
   Run grep search across the codebase for the deleted class/module names:
   ```bash
   grep -rn "PlatformEmulator" f:\Projects\alpha_farm
   grep -rn "SubmitStrategies" f:\Projects\alpha_farm
   grep -rn "SandboxPrefixer" f:\Projects\alpha_farm
   grep -rn "RestrictedSeries" f:\Projects\alpha_farm
   ```
   *Verification condition*: Should return 0 matches in active Python codebase (excluding `.agents/` and historical documentation if preserved).

2. **Pytest Execution**:
   Run the pytest test suite:
   ```bash
   pytest
   ```
   *Verification condition*: 0 collection errors, 0 test failures across `test_core_engine.py`, `test_mcts_engine.py`, `test_semantic_compiler.py`, `test_hmm_validation.py`, and `test_hardware_concurrency.py`.
