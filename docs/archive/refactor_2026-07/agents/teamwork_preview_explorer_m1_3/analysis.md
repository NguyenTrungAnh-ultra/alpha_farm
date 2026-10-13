# Analysis Report: Legacy Sandbox Investigation & Refactoring Plan (Milestone 1)

**Target Directory**: `core_engine/`  
**Explorer**: Explorer 3 (Milestone 1)  
**Date**: 2026-07-21  

---

## 1. Investigation of `core_engine/` Sandbox Components

### 1.1 `RestrictedSeries` (`core_engine/RestrictedSeries.py`)
- **Historical Purpose**: Custom wrapper class around `pd.Series` designed to emulate the AST and runtime restrictions of the XNOQuant competition web sandbox.
- **Key Implementation Details**:
  - **Attribute/Method Access Blocking**: `__getattr__` intercepts any non-private attribute or method call (e.g., `.mean()`, `.rolling()`, `.iloc`). If the method is not explicitly whitelisted, it raises an `AttributeError` instructing the user to use `self.feat` or `self.op`.
  - **Physical Indexing Interception**: `__getitem__` intercepts bracket indexing (e.g., `series[idx]`) and raises a `TypeError` prohibiting direct index access.
  - **Whitelisted Causal Methods**: Exposes a minimal set of pandas methods: `fillna` (rejecting `bfill`), `ffill`, `where`, `pct_change`, `shift`, `diff`, `astype`.
  - **Operator Overloading**: Overloads arithmetic (`+`, `-`, `*`, `/`, `**`), comparative (`>`, `<`, `>=`, `<=`, `==`, `!=`), logical (`&`, `|`, `~`), and unary (`abs`, `-`, `+`) operators. Every operation unwraps operands via `_unwrap()`, performs calculations on the underlying `pd.Series`, and re-wraps the result into a new `RestrictedSeries` via `_wrap()`.
- **Architectural Impact**: Causes continuous object creation, wrapper overhead, and unnecessary indirection during strategy evaluations and backtesting loops.

### 1.2 `FeatureEngine` (`core_engine/XnoEngine.py`)
- **Historical Purpose**: Mocks `self.feat.*` for strategy expressions.
- **Key Implementation Details**:
  - **Custom Functions**: Implements 16 basic rolling functions (`rolling_mean`, `rolling_max`, `rolling_min`, `rolling_std`, `rolling_sum`, `rolling_rank`, `rolling_percentile_rank`, `rolling_median`, `rolling_quantile`, `rolling_correlation`, `rolling_covariance`, `rolling_zscore`, `rolling_mad`, `rolling_argmax`, `rolling_argmin`, `rolling_prod`).
  - **Statistical & Custom Volume/Price Functions**: Implements indicators such as `zscore`, `price_z`, `volume_z`, `returns`, `log_returns`, `donchian_upper`, `donchian_lower`, `hlc3`, `ohlc4`, `vwap`, `rolling_vwap`, `cmf`.
  - **TA-Lib Fallback**: `__getattr__` dynamically resolves non-explicit functions to TA-Lib functions using `_load_feature_whitelist()` (reading `feature.txt`) and `_wrap_normalize_params()` to adjust parameter names (`window`, `timeperiod`).
  - **Wrapping/Unwrapping Cycle**: Every method unwraps `RestrictedSeries` inputs using `_unwrap()`, performs computation via pandas/numpy/talib, and re-wraps outputs in `RestrictedSeries` via `_wrap()`.

### 1.3 `OperatorEngine` (`core_engine/XnoEngine.py`)
- **Historical Purpose**: Mocks `self.op.*` for 30 logical, comparison, and causal operators.
- **Key Implementation Details**:
  - Implements operators: `crossed`, `crossed_above`, `crossed_below`, `current`, `previous`, `shift`, `diff`, `pct_change`, `rising`, `falling`, `fillna`, `ffill`, `abs`, `clip`, `isna`, `notna`, `isfinite`, `zero_ifna`, `sign`, `replace`, `between`, `where`, `value_when`, `bars_since`, `hold_for`, `crossed_above_value`, `crossed_below_value`, `and_`, `or_`, `not_`.
  - Enforces causal safety checks (e.g., verifying `periods > 0` for `shift`, `diff`, `pct_change` and throwing errors for `bfill`).
  - Converts inputs using `_unwrap()` and return values using `_wrap()`.

### 1.4 `SimpleAlgorithm` and `DataProxy` (`core_engine/XnoEngine.py`)
- **`DataProxy`**: Wraps DataFrame columns (`Open`, `High`, `Low`, `Close`, `Volume`) into `RestrictedSeries` instances (`pv_open`, `pv_high`, `pv_low`, `pv_close`, `pv_volume`).
- **`SimpleAlgorithm`**:
  - Base class managing initialization of `self.data`, `self.feat`, `self.op`.
  - `_validate_sandbox_constraints()` performs AST parsing (`ast.parse`) and Python bytecode inspection (`dis.get_instructions`) to reject subclass constructors (`__init__`), extra helper functions, `open()`, `getattr()`, and module imports.

---

## 2. Analysis of `RestrictedSeries` Usage & Plain Pandas/Numpy Replacements

### 2.1 Current Usage in Calculation Flow
1. **Data Initialization**: `DataProxy` converts raw DataFrame columns (`df['Open']`) into `RestrictedSeries`.
2. **Indicator Computation**: `FeatureEngine` and `OperatorEngine` receive `RestrictedSeries` arguments, extract `arg._data`, compute pandas/numpy results, and wrap the output back into `RestrictedSeries`.
3. **Strategy Signal Output**: Strategy `__algorithm__` produces target position series wrapped as `RestrictedSeries`.
4. **Backtest Execution**: `XNOBacktestEngine.run()` calls `strategy.run_algorithm(df)` and explicitly unwraps `positions._data` at line 196-197:
   ```python
   if type(positions).__name__ == 'RestrictedSeries':
       positions = positions._data
   ```

### 2.2 Performance Overhead Analysis
- **Memory & Allocation Overhead**: A single strategy evaluation involving multiple indicators generates dozens to hundreds of transient `RestrictedSeries` objects.
- **Call Stack Indirection**: Every arithmetic operation (`+`, `-`, `*`, `/`) incurs custom Python method lookup (`__add__`, `_unwrap`, `_wrap`) rather than executing directly at C-speed in Pandas/NumPy.

### 2.3 Replacement Strategy using Native Pandas/NumPy Types (`pd.Series`, `np.ndarray`)

| Location | Legacy Type | Proposed Native Replacement | Rationale |
|---|---|---|---|
| `DataProxy` fields (`pv_open`, `pv_high`, etc.) | `RestrictedSeries` | `pd.Series` (or `np.ndarray`) | Eliminates wrapper object instantiation. Standard `pd.Series` supports all math operations natively. |
| Engine calculations (`FeatureEngine` / `AlphaPrimitives`) | Inputs/Outputs wrapped in `RestrictedSeries` | `pd.Series` or `np.ndarray` | Direct array and vectorized operations eliminate call stack indirection. |
| Strategy `run_algorithm()` return value | `RestrictedSeries` | `pd.Series` | `BacktestEngine.py` expects a 1D time-series indexed by `df.index`. `pd.Series` handles `.shift(1)` and `.fillna(0.0)` natively. |
| `BacktestEngine.py` (lines 196-197) | Unwrapping `RestrictedSeries` | Direct `pd.Series` processing | Safe deletion of `if type(positions).__name__ == 'RestrictedSeries': positions = positions._data`. |

---

## 3. Step-by-Step Removal and Refactoring Plan

### Phase 1: Physical File Removal (4 Files)
Delete the following 4 files that represent legacy web sandbox components:
1. `core_engine/RestrictedSeries.py`
2. `core_engine/PlatformEmulator.py`
3. `strategy_workflows/SubmitStrategies.py`
4. `utilities/SandboxPrefixer.py`

### Phase 2: Dependency Cleanup & Code Refactoring
1. **`core_engine/BacktestEngine.py`**:
   - Delete lines 196-197 (`if type(positions).__name__ == 'RestrictedSeries': positions = positions._data`).
2. **`core_engine/XnoEngine.py`**:
   - Remove `from .RestrictedSeries import RestrictedSeries`.
   - In `FeatureEngine` and `OperatorEngine`: remove `_unwrap` and `_wrap` calls; operate on and return standard `pd.Series`.
   - In `DataProxy`: initialize `pv_open`, `pv_high`, `pv_low`, `pv_close`, `pv_volume` as standard `pd.Series` (`df['Open']`, etc.).
   - In `SimpleAlgorithm.set_positions`: remove `RestrictedSeries` type check on `mask`.
3. **`strategy_workflows/HMMValidation.py`**:
   - Remove `from core_engine.PlatformEmulator import XNOPlatformEmulator` at line 23.
   - Replace `emulator = XNOPlatformEmulator()` (line 285) with `engine = XNOBacktestEngine()`.
   - Replace `emulator.engine.run(strategy, sim_df)` (lines 297, 396) with `engine.run(strategy, sim_df)`.
4. **`main.py`**:
   - Remove `from strategy_workflows.SubmitStrategies import run_auto_submit` in `cmd_submit`.
   - Remove `cmd_submit` and the `submit` option from CLI interactive menu and `argparse` subparsers.
5. **`refactor_imports.py`**:
   - Remove regex rules targeting `RestrictedSeries`, `PlatformEmulator`, `SubmitStrategies`, `SandboxPrefixer`.

### Phase 3: Verification & Validation
1. **Unit Test Suite Execution**:
   - Run `pytest tests/test_core_engine.py` to ensure `BacktestEngine` correctly processes strategies returning `pd.Series` and `np.ndarray`.
2. **Codebase Grep Verification**:
   - Perform project-wide regex search for `RestrictedSeries`, `PlatformEmulator`, `SubmitStrategies`, `SandboxPrefixer` to confirm zero remaining active code references.
