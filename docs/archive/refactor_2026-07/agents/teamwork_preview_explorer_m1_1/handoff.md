# Handoff Report: Milestone 1 Sandbox & Legacy Traces Audit

## 1. Observation
Direct search and code inspection across `f:\Projects\alpha_farm` revealed:
- **Files to be deleted (4 files)**:
  1. `f:\Projects\alpha_farm\core_engine\PlatformEmulator.py` (189 lines, defines `XNOPlatformEmulator`)
  2. `f:\Projects\alpha_farm\strategy_workflows\SubmitStrategies.py` (817 lines, defines `run_auto_submit`, `format_code_for_xno`, Playwright auto-submit logic)
  3. `f:\Projects\alpha_farm\utilities\SandboxPrefixer.py` (387 lines, defines `apply_prefixes`, `check_tautology`)
  4. `f:\Projects\alpha_farm\core_engine\RestrictedSeries.py` (164 lines, defines `RestrictedSeries`)
- **Direct import and usage locations**:
  - `strategy_workflows/HMMValidation.py`:
    - Line 23: `from core_engine.PlatformEmulator import XNOPlatformEmulator`
    - Line 285: `emulator = XNOPlatformEmulator()`
    - Lines 297 & 396: `res = emulator.engine.run(strategy, sim_df)`
  - `main.py`:
    - Line 9: Docstring reference to `submit`
    - Line 92: `from strategy_workflows.SubmitStrategies import run_auto_submit`
    - Line 110: `success, err_msg = run_auto_submit(...)`
    - Line 130: `cmd_submit(args)` in `cmd_full(args)`
    - Lines 269, 305-306, 337, 369-370: CLI & interactive menu entries for `submit`
  - `core_engine/BacktestEngine.py`:
    - Lines 195-197: `if type(positions).__name__ == 'RestrictedSeries': positions = positions._data`
  - `strategy_workflows/RunMCTS.py`:
    - Line 177: `logging.getLogger("core_engine.RestrictedSeries").setLevel(logging.CRITICAL)`
  - `core_engine/XnoEngine.py`:
    - Line 24: `from .RestrictedSeries import RestrictedSeries`
    - Lines 178, 184, 434, 485, 488, 506, 512: `RestrictedSeries` checks and returns in `FeatureEngine`
    - Lines 516-764: Type hints and return annotations `-> RestrictedSeries` across `OperatorEngine`
    - Lines 778-781: `self.pv_open = RestrictedSeries(df['Open'])`, etc., in `SimpleAlgorithm`
  - `refactor_imports.py`:
    - Lines 40-42, 44-46, 64-66, 100-102: Migration rules referencing `PlatformEmulator`, `RestrictedSeries`, `SubmitStrategies`, `SandboxPrefixer`.
- **Test suite (`tests/`)**:
  - 0 occurrences of `PlatformEmulator`, `SubmitStrategies`, `SandboxPrefixer`, or `RestrictedSeries` in `tests/`.

## 2. Logic Chain
1. **Observation**: `PlatformEmulator.py` is imported by `strategy_workflows/HMMValidation.py` (line 23) to instantiate `emulator` (line 285).
   - **Reasoning**: `HMMValidation.py` only invokes `emulator.engine.run(strategy, sim_df)` on lines 297 & 396. `emulator.engine` is `XNOBacktestEngine`.
   - **Step**: Replace `XNOPlatformEmulator` with `XNOBacktestEngine` from `core_engine.BacktestEngine` in `HMMValidation.py`.
2. **Observation**: `SubmitStrategies.py` is imported by `main.py` (line 92) inside `cmd_submit`.
   - **Reasoning**: `SubmitStrategies.py` provides Playwright web submission logic. In Milestone 1, web submission is obsolete.
   - **Step**: Delete `SubmitStrategies.py` and prune `cmd_submit`, `cmd_full`'s submit step, interactive menu options, and CLI subparsers from `main.py`.
3. **Observation**: `SandboxPrefixer.py` has zero active imports in python source files, only legacy migration rules in `refactor_imports.py`.
   - **Reasoning**: `SandboxPrefixer.py` was used to rewrite expressions for XNO sandbox compatibility, which is no longer needed.
   - **Step**: Safe to delete `SandboxPrefixer.py` immediately.
4. **Observation**: `RestrictedSeries.py` is referenced in `BacktestEngine.py`, `RunMCTS.py`, and `XnoEngine.py`.
   - **Reasoning**: `RestrictedSeries` wrapped `pandas.Series` to throw errors on disallowed methods during web sandbox evaluation. Pure Numpy/Pandas operation relies on unwrapped `pd.Series` and `np.ndarray`.
   - **Step**: Remove unwrapping checks in `BacktestEngine.py` (lines 195-197), remove logger line in `RunMCTS.py` (line 177), and unwrap `RestrictedSeries` in `XnoEngine.py` (`self.pv_open = df['Open']`).

## 3. Caveats
- `core_engine/XnoEngine.py` contains extensive references to `RestrictedSeries` in docstrings and type hints. While full engine refactoring into `AlphaEngine.py` takes place in Milestone 3, removing `RestrictedSeries` imports and replacing `RestrictedSeries(df['Open'])` with `df['Open']` in `SimpleAlgorithm` is necessary in Milestone 1 to prevent import errors once `RestrictedSeries.py` is deleted.

## 4. Conclusion
All 4 legacy sandbox files (`PlatformEmulator.py`, `SubmitStrategies.py`, `SandboxPrefixer.py`, `RestrictedSeries.py`) can be safely deleted once the identified references in `strategy_workflows/HMMValidation.py`, `main.py`, `core_engine/BacktestEngine.py`, `strategy_workflows/RunMCTS.py`, `core_engine/XnoEngine.py`, and `refactor_imports.py` are cleaned up. Detailed line-by-line instructions are provided in `analysis.md`.

## 5. Verification Method
1. **File Deletion Verification**:
   Verify the 4 target files are removed:
   ```powershell
   Test-Path f:\Projects\alpha_farm\core_engine\PlatformEmulator.py
   Test-Path f:\Projects\alpha_farm\strategy_workflows\SubmitStrategies.py
   Test-Path f:\Projects\alpha_farm\utilities\SandboxPrefixer.py
   Test-Path f:\Projects\alpha_farm\core_engine\RestrictedSeries.py
   ```
   All must return `False`.

2. **Codebase Zero-Occurrence Check**:
   Search the entire repository for any remaining imports or class references:
   ```powershell
   grep -r "PlatformEmulator" f:\Projects\alpha_farm --exclude-dir=.agents --exclude=analysis.md --exclude=handoff.md
   grep -r "SubmitStrategies" f:\Projects\alpha_farm --exclude-dir=.agents --exclude=analysis.md --exclude=handoff.md
   grep -r "SandboxPrefixer" f:\Projects\alpha_farm --exclude-dir=.agents --exclude=analysis.md --exclude=handoff.md
   grep -r "RestrictedSeries" f:\Projects\alpha_farm --exclude-dir=.agents --exclude=analysis.md --exclude=handoff.md
   ```
   All commands must return 0 results in active python code.

3. **Pytest Verification**:
   Run `pytest` across the repo to verify no import or runtime errors occur.
