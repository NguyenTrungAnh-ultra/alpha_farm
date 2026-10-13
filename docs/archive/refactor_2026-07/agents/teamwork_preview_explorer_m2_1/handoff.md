# Handoff Report: Milestone 2 AlphaPrimitives Interface Design

**From**: Explorer 1 (`teamwork_preview_explorer_m2_1`)  
**To**: Parent Agent / Milestone 2 Worker  
**Date**: 2026-07-21  

---

## 1. Observation

- **Task Scope**: Design the module interface, function signatures, type compatibility rules, NaN padding rules, and mathematical specifications for `core_engine/AlphaPrimitives.py` in Milestone 2.
- **Required Primitives**: `ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, `ts_argmin`.
- **Existing Infrastructure**:
  - `PROJECT.md` line 8: Specifies high-performance time-series operations using vectorized NumPy.
  - `orchestrator/plan.md` lines 12-15: Defines Milestone 2 scope for primitive creation and benchmarking.
- **Analysis Artifact**: Written to `f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_1\analysis.md`.

---

## 2. Logic Chain

1. **Problem Context**: MCTS strategy discovery in `alpha_farm` requires fast, mathematically exact time-series primitives without the overhead of Python loops or Pandas `.rolling().apply()` calls.
2. **Type Compatibility Architecture**:
   - Both `pd.Series` and `np.ndarray` inputs must be handled seamlessly.
   - Using a standardized wrapper (`@ts_primitive` / input helper) extracts raw 1D NumPy arrays, validates parameters, and re-wraps output into `pd.Series` (preserving `x.index` and `x.name`) if the input was a Pandas Series.
3. **Leading NaN Padding Protocol**:
   - Output length must strictly equal input length $N$.
   - For window size $d$, indices $0$ to $d-2$ are padded with `np.nan`.
   - Calculations for index $i \ge d-1$ operate over window $x[i-d+1 : i+1]$.
4. **NumPy Vectorization via Striding**:
   - Utilizing `np.lib.stride_tricks.sliding_window_view(arr, window_shape=d)` provides a 2D zero-copy strided view of shape $(N-d+1, d)$.
   - All primitive kernels (`mean`, `sum`, `max`, `min`, `rank`, `corr`, `zscore`, `argmax`, `argmin`) execute across `axis=1` in compiled C/NumPy loops.
5. **Numerical Stability & Edge Case Handling**:
   - `ts_rank` calculates percentile rank with tie-handling matching Pandas `rank(pct=True)`.
   - `ts_argmax` and `ts_argmin` return 1-based index positions within window $[1, d]$.
   - `ts_zscore` handles zero variance by returning `0.0` when standard deviation $< 10^{-12}$.
   - `ts_corr` clips correlations to $[-1.0, 1.0]$ and handles zero-variance inputs safely.
   - Any internal `np.nan` inside a rolling window propagates to output `np.nan`.

---

## 3. Caveats

- **NumPy Version Requirement**: Relies on `np.lib.stride_tricks.sliding_window_view`, available in NumPy 1.20+.
- **Read-Only Scope**: In accordance with the explorer archetype, no production code in `core_engine/AlphaPrimitives.py` was created or modified directly. Implementation should be carried out by the worker agent using `analysis.md`.
- **Memory Footprint**: `sliding_window_view` creates a zero-copy view, but reduction operations generate a 1D result array of length $N-d+1$. Memory overhead is $O(N)$, which is optimal.

---

## 4. Conclusion

The module interface, function signatures, mathematical specifications, input/output type compatibility mechanisms, NaN padding rules, edge-case validation, and vectorization design for `core_engine/AlphaPrimitives.py` are complete and fully documented in `analysis.md`.

---

## 5. Verification Method

To verify this design before and during implementation:

1. **Inspect Artifacts**:
   - File exists: `f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_1\analysis.md`.
   - Detailed signatures, docstrings, vectorization kernels, and edge cases are documented for all 9 primitive functions (`ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, `ts_argmin`).
2. **Implementation & Unit Test Verification**:
   - Upon worker implementation of `core_engine/AlphaPrimitives.py`, run pytest unit tests against Pandas `.rolling()` baselines:
     ```powershell
     pytest tests/test_alpha_primitives.py
     ```
   - Run benchmark script to verify mathematical equivalence within $10^{-6}$ tolerance and speedup:
     ```powershell
     python benchmark_primitives.py
     ```
