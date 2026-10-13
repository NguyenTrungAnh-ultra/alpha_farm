# Milestone 1 Analysis Report: Erase Sandbox & Legacy Traces

## 1. Executive Summary
This report presents a complete audit of all legacy competition web sandbox files targeted for deletion in **Milestone 1** of the `alpha_farm` refactoring project. 
The 4 target modules to be deleted are:
1. `core_engine/PlatformEmulator.py`
2. `strategy_workflows/SubmitStrategies.py`
3. `utilities/SandboxPrefixer.py`
4. `core_engine/RestrictedSeries.py`

All repo references across `main.py`, `core_engine/`, `strategy_workflows/`, `utilities/`, `tests/`, `scratch/`, and migration scripts have been cataloged with exact line numbers and cleanup actions.

---

## 2. Deletion Target Inventory

| File Path | Line Count | Core Responsibility | Downstream Dependent Files |
|-----------|------------|---------------------|----------------------------|
| `core_engine/PlatformEmulator.py` | 189 | XNOQuant web sandbox emulator (`XNOPlatformEmulator`). | `strategy_workflows/HMMValidation.py`, `refactor_imports.py` |
| `strategy_workflows/SubmitStrategies.py` | 817 | Playwright web submission automation (`run_auto_submit`, `format_code_for_xno`). | `main.py`, `refactor_imports.py` |
| `utilities/SandboxPrefixer.py` | 387 | AST/Regex prefixing tool (`apply_prefixes`, `check_tautology`). | `refactor_imports.py` |
| `core_engine/RestrictedSeries.py` | 164 | Custom `pandas.Series` wrapper simulating sandbox AST locks. | `core_engine/BacktestEngine.py`, `strategy_workflows/RunMCTS.py`, `core_engine/XnoEngine.py`, `refactor_imports.py` |

---

## 3. Detailed Reference Audit & Impact Analysis

### A. `PlatformEmulator.py` / `XNOPlatformEmulator`
- **File**: `core_engine/PlatformEmulator.py` (Delete file)
- **File**: `strategy_workflows/HMMValidation.py`
  - **Line 23**: `from core_engine.PlatformEmulator import XNOPlatformEmulator`
  - **Line 285**: `emulator = XNOPlatformEmulator()`
  - **Line 297**: `res = emulator.engine.run(strategy, sim_df)`
  - **Line 396**: `res = emulator.engine.run(strategy, sim_df)`
  - *Impact*: `HMMValidation.py` instantiates `XNOPlatformEmulator` solely to access its `.engine` attribute (which is `XNOBacktestEngine`).
  - *Required Fix*: 
    - Replace line 23 import with `from core_engine.BacktestEngine import XNOBacktestEngine`.
    - Replace `emulator = XNOPlatformEmulator()` on line 285 with `engine = XNOBacktestEngine()`.
    - Change lines 297 & 396 to `res = engine.run(strategy, sim_df)`.
- **File**: `refactor_imports.py`
  - **Lines 40-42**: Import migration rules for `xno_sdk.emulator`.
  - *Required Fix*: Remove lines 40-42.
- **Documentation**:
  - `README.md` (Line 40): Remove `mcts_sandbox[PlatformEmulator]` node.
  - `docs/ARCH.md` (Line 51): Remove paragraph describing `PlatformEmulator.py`.

---

### B. `SubmitStrategies.py` / `run_auto_submit`
- **File**: `strategy_workflows/SubmitStrategies.py` (Delete file)
- **File**: `main.py`
  - **Line 9**: Module docstring mentioning `3. submit: Submits successful, qualified strategies...`
  - **Lines 79-115**: Function `cmd_submit(args)` importing `from strategy_workflows.SubmitStrategies import run_auto_submit`.
  - **Line 130**: Function call `cmd_submit(args)` inside `cmd_full(args)`.
  - **Line 269**: Interactive menu prompt string `"submit (Tự động nộp chiến lược lên XNO)"`.
  - **Lines 305-306**: Menu selection dispatch `elif selected_cmd == "submit": cmd_submit(args)`.
  - **Line 337**: CLI argparse parser `parser_sub = subparsers.add_parser("submit", ...)`
  - **Lines 369-370**: Command router `elif args.command == "submit": cmd_submit(args)`
  - *Impact*: `main.py` relies on `SubmitStrategies.py` for its `submit` subcommand.
  - *Required Fix*: 
    - Remove `cmd_submit` function definition (lines 79-115).
    - Update `cmd_full` (line 130) to only execute `cmd_generate(args)` and `cmd_mcts(args)`.
    - Remove `submit` option from interactive menu list, menu handler, CLI subparsers, and execution router.
- **File**: `refactor_imports.py`
  - **Lines 64-66**: Import migration rules for `agent.auto_submit`.
  - *Required Fix*: Remove lines 64-66.
- **Documentation**:
  - `README.md` (Line 46): Remove `auto_sub(SubmitStrategies.py)` node.
  - `docs/ARCH.md` (Line 47): Remove paragraph describing `SubmitStrategies.py`.

---

### C. `SandboxPrefixer.py` / `apply_prefixes`
- **File**: `utilities/SandboxPrefixer.py` (Delete file)
- **File**: `refactor_imports.py`
  - **Lines 100-102**: Import migration rules for `agent.sandbox_prefixer`.
  - *Required Fix*: Remove lines 100-102.
- **Documentation**:
  - `docs/ARCH.md` (Line 77): Remove reference to `utilities/SandboxPrefixer.py`.
- **Note**: No active python runtime files import `SandboxPrefixer.py`.

---

### D. `RestrictedSeries.py` / `RestrictedSeries`
- **File**: `core_engine/RestrictedSeries.py` (Delete file)
- **File**: `core_engine/BacktestEngine.py`
  - **Lines 195-197**:
    ```python
    # Unwrap RestrictedSeries if returned by strategy
    if type(positions).__name__ == 'RestrictedSeries':
        positions = positions._data
    ```
  - *Impact*: Legacy type-check to unwrap `RestrictedSeries`.
  - *Required Fix*: Delete lines 195-197. `positions` is directly a `pd.Series` or `np.ndarray`.
- **File**: `strategy_workflows/RunMCTS.py`
  - **Line 177**: `logging.getLogger("core_engine.RestrictedSeries").setLevel(logging.CRITICAL)`
  - *Impact*: Silences non-existent logger.
  - *Required Fix*: Delete line 177.
- **File**: `core_engine/XnoEngine.py`
  - **Line 24**: `from .RestrictedSeries import RestrictedSeries`
  - **Lines 114-115, 178, 184, 434, 485, 488, 506, 512**: Internal checks and returns of `RestrictedSeries` in `FeatureEngine`.
  - **Lines 516-764**: Method signatures and return annotations `-> RestrictedSeries` in `OperatorEngine`.
  - **Lines 773, 778-781**: Initializing `self.pv_open = RestrictedSeries(df['Open'])` in `SimpleAlgorithm`.
  - *Impact*: `XnoEngine.py` wraps Series in `RestrictedSeries`.
  - *Required Fix*: 
    - Remove line 24 import.
    - Replace `RestrictedSeries(...)` wrappers with native `pd.Series` or `np.ndarray`.
    - Change `self.pv_open = df['Open']`, etc.
- **File**: `refactor_imports.py`
  - **Lines 44-46**: Import migration rules for `xno_sdk.series`.
  - *Required Fix*: Remove lines 44-46.
- **Test Suite Check**:
  - `tests/`: 0 occurrences found.

---

## 4. Proposed Modifications Checklist for Implementer

1. **Delete Files**:
   - `core_engine/PlatformEmulator.py`
   - `strategy_workflows/SubmitStrategies.py`
   - `utilities/SandboxPrefixer.py`
   - `core_engine/RestrictedSeries.py`

2. **Refactor Code References**:
   - `strategy_workflows/HMMValidation.py`: Replace `XNOPlatformEmulator` with `XNOBacktestEngine`.
   - `main.py`: Remove `cmd_submit` and all CLI / menu references to `submit`.
   - `core_engine/BacktestEngine.py`: Remove `RestrictedSeries` unwrapping check (lines 195-197).
   - `strategy_workflows/RunMCTS.py`: Remove `RestrictedSeries` logger line (line 177).
   - `core_engine/XnoEngine.py`: Remove `from .RestrictedSeries import RestrictedSeries`, unwrap `RestrictedSeries` instantiation in `SimpleAlgorithm` (`self.pv_open = df['Open']`), and update `FeatureEngine`/`OperatorEngine` return values.
   - `refactor_imports.py`: Delete regex rules for `emulator`, `auto_submit`, `sandbox_prefixer`, `series`.

3. **Documentation Updates**:
   - Update `README.md` and `docs/ARCH.md` to remove descriptions/diagrams of deleted modules.
