## 2026-07-21T13:23:51+07:00

You are worker_m2 for Milestone 2 (Implement AlphaPrimitives & Benchmark) in alpha_farm refactoring.
Working directory: f:\Projects\alpha_farm\.agents\teamwork_preview_worker_m2
Project file: f:\Projects\alpha_farm\PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Task:
1. Read the design specs in:
   - f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_1\analysis.md
   - f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_2\analysis.md
   - f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_3\analysis.md
2. Create `core_engine/AlphaPrimitives.py` implementing all 9 high-performance vectorized NumPy primitive functions:
   - `ts_mean(x, d)`
   - `ts_sum(x, d)`
   - `ts_max(x, d)`
   - `ts_min(x, d)`
   - `ts_rank(x, d)`
   - `ts_corr(x, y, d)`
   - `ts_zscore(x, d)`
   - `ts_argmax(x, d)`
   - `ts_argmin(x, d)`
   Ensure zero slow Python loops over time steps using `np.lib.stride_tricks.sliding_window_view`. Support both pd.Series and np.ndarray. Pad leading `d - 1` entries with `np.nan`.
3. Create `benchmark_primitives.py` at repository root:
   - Compare all 9 AlphaPrimitives against naive Pandas `.rolling()` baselines.
   - Assert numerical equivalence within 1e-5 tolerance using `np.allclose(..., equal_nan=True)`.
   - Measure execution time (ms) and speedup multiplier (x) for N=10000, d=20.
4. Execute `python benchmark_primitives.py` and `pytest tests/` using run_command or Python execution.
5. Write complete handoff report to `f:\Projects\alpha_farm\.agents\teamwork_preview_worker_m2\handoff.md` with benchmark output table and test verification results. Send completion message to parent.
