# Handoff Report: Milestone 3 Engine Refactoring Analysis

## 1. Observation

Direct observations from examining `core_engine/XnoEngine.py` and `core_engine/BacktestEngine.py`:

- **`core_engine/XnoEngine.py`** (961 lines, 40,940 bytes):
  - **Imports**: Line 20: `import talib` (C-extension TA-Lib binding); Line 22: `import os`; Line 23: `import re`.
  - **Logger**: Line 24: `logger = logging.getLogger("core_engine.XnoEngine")`.
  - **Whitelist Parsing**: Lines 26-77: `_load_feature_whitelist()` reads `feature.txt` or `docs/feature.txt` via regex `re.findall(r"self\.feat\.([a-zA-Z0-9_]+)\s*\(", content)` or returns fallback whitelist of 74 function strings.
  - **Pattern Mapping**: Lines 79-105: `TALIB_NAME_MAPPING` maps 25 snake_case candlestick pattern names to TA-Lib function names.
  - **`FeatureEngine` Class**: Lines 107-490: 383 lines mocking `self.feat.*`, dynamic method wrapping via `_wrap_normalize_params`, 27 custom rolling/statistical functions, and dynamic TA-Lib fallback via `__getattr__`.
  - **`OperatorEngine` Class**: Lines 491-760: 269 lines mocking `self.op.*`, implementing 30 custom logical/causal operators (`shift`, `diff`, `pct_change`, `crossed`, `value_when`, `bars_since`, etc.).
  - **`DataProxy` Class**: Lines 761-781: Stores `_df`, `pv_open`, `pv_high`, `pv_low`, `pv_close`, `pv_volume`.
  - **`SimpleAlgorithm` Class**: Lines 782-961: Base class instantiating `DataProxy`, `FeatureEngine`, and `OperatorEngine`. Lines 819-952: `_validate_sandbox_constraints()` parses AST and inspects bytecode for forbidden constructors, helper functions, `open`, `getattr`, and `import` instructions.

- **`core_engine/BacktestEngine.py`** (474 lines, 19,853 bytes):
  - **Data Classes**: Lines 33-76: `TradeRecord`; Lines 79-110: `BacktestResult`.
  - **`XNOBacktestEngine` Class**: Lines 112-440: Simulates VN30F futures market: 28.5% initial margin, 18.5% maintenance margin, 6,000 VND fee per contract per side, intra-bar margin call liquidations, 3rd-Thursday contract rollover penalties, and mark-to-market equity curve.
  - **Strategy Execution**: Line 193: `positions = strategy.run_algorithm(df)`; Line 198: `positions = positions.shift(1).fillna(0.0)`.

---

## 2. Logic Chain

1. **Observation 1**: `core_engine/XnoEngine.py` contains `import talib`, `_load_feature_whitelist()`, `TALIB_NAME_MAPPING`, `FeatureEngine` (Lines 107-490), `OperatorEngine` (Lines 491-760), and `_validate_sandbox_constraints()` (Lines 819-952).
2. **Step 1**: In Milestone 3, all strategy calculations operate on pure Numpy primitives (`AlphaPrimitives.py`) or direct Pandas/Numpy operations without sandbox AST inspection or TA-Lib bindings. Therefore, `FeatureEngine`, `OperatorEngine`, `import talib`, `_load_feature_whitelist()`, `TALIB_NAME_MAPPING`, and `_validate_sandbox_constraints()` must be deleted entirely.
3. **Observation 2**: `DataProxy` (Lines 761-781) and `SimpleAlgorithm` (Lines 782-818, 954-961) provide the strategy data container and position-setting interface (`set_positions`).
4. **Step 2**: Rename `DataProxy` to `AlphaDataProxy` and `SimpleAlgorithm` to `AlphaStrategy`. Provide aliases `DataProxy = AlphaDataProxy` and `SimpleAlgorithm = AlphaStrategy` for backward compatibility. Strip `self.feat` and `self.op` instantiations from `_initialize`.
5. **Observation 3**: `core_engine/BacktestEngine.py` cleanly encapsulates VN30F futures margin, netting fees, intra-bar margin call liquidations, and rollover penalty calculations via `XNOBacktestEngine`.
6. **Step 3**: Create class `AlphaEngine` in `core_engine/AlphaEngine.py` as a facade wrapping `XNOBacktestEngine`. Expose `AlphaEngine.run(strategy, df)` to generate `BacktestResult` and `AlphaEngine.evaluate(strategy, df)` to compute strategy risk/performance metrics via `CalculateMetrics.compute_metrics()`.

---

## 3. Caveats

- **Backward Compatibility Aliases**: Existing strategies and tests that import `DataProxy` or `SimpleAlgorithm` will continue to function seamlessly if `DataProxy = AlphaDataProxy` and `SimpleAlgorithm = AlphaStrategy` are defined as top-level aliases in `core_engine/AlphaEngine.py`.
- **`feature.txt` File**: The whitelist file `feature.txt` (or `docs/feature.txt`) is obsolete once `FeatureEngine` is removed.
- **`BacktestEngine.py` Scope**: `core_engine/BacktestEngine.py` requires no internal code modifications; it is retained intact and integrated directly into `AlphaEngine.py`.

---

## 4. Conclusion

`core_engine/XnoEngine.py` can be refactored into `core_engine/AlphaEngine.py` by:
1. Deleting `import talib`, `import os`, `import re`, `_load_feature_whitelist()`, `TALIB_NAME_MAPPING`, `FeatureEngine`, `OperatorEngine`, and `_validate_sandbox_constraints()`.
2. Refactoring `DataProxy` to `AlphaDataProxy` and `SimpleAlgorithm` to `AlphaStrategy` (retaining backward-compatibility aliases).
3. Defining class `AlphaEngine` incorporating `XNOBacktestEngine` from `core_engine.BacktestEngine` and `compute_metrics` from `core_engine.CalculateMetrics`.

---

## 5. Verification Method

- **Static Code Inspection**:
  - Run `grep_search` on `core_engine/AlphaEngine.py` to confirm 0 occurrences of `talib`, `FeatureEngine`, `OperatorEngine`, or `_validate_sandbox_constraints`.
  - Confirm `AlphaEngine` imports `XNOBacktestEngine` from `core_engine.BacktestEngine`.
- **Pytest Suite Verification**:
  - Execute `pytest tests/` in terminal to confirm all core engine and strategy execution tests pass with 0 errors.
