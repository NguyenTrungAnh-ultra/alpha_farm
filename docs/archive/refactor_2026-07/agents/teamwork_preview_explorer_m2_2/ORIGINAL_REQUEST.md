## 2026-07-21T06:21:10Z
You are explorer 2 for Milestone 2 (Implement AlphaPrimitives & Benchmark) in alpha_farm refactoring.
Working directory: f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_2
Project file: f:\Projects\alpha_farm\PROJECT.md

Task:
1. Design ultra-fast vectorized NumPy implementations for all 9 primitives using `np.lib.stride_tricks.sliding_window_view`.
2. Detail high-performance formulas for:
   - `ts_mean(x, d)`, `ts_sum(x, d)`, `ts_max(x, d)`, `ts_min(x, d)`
   - `ts_rank(x, d)` (percentile rank within rolling window)
   - `ts_corr(x, y, d)` (rolling Pearson correlation)
   - `ts_zscore(x, d)` ((x - mean)/std within rolling window)
   - `ts_argmax(x, d)`, `ts_argmin(x, d)` (index offset of max/min in rolling window)
3. Ensure zero slow Python loops over time steps.
4. Write your analysis report to f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_2\analysis.md and write handoff.md. Send completion message to parent.
