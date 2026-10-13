# Handoff Report: Milestone 2 — `benchmark_primitives.py` Design

**Agent**: Explorer 3  
**Working Directory**: `f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_3`  
**Target File**: `benchmark_primitives.py` (Repository Root)  
**Milestone**: Milestone 2 — Implement AlphaPrimitives & Benchmark  

---

## 1. Observation

- **Project Specification (`PROJECT.md` line 16, 29)**:
  `PROJECT.md` explicitly lists Milestone 2 scope: *"Create core_engine/AlphaPrimitives.py with fast Numpy operators + benchmark_primitives.py verification script"*, and code layout line 29: *"benchmark_primitives.py: Benchmark script comparing AlphaPrimitives against Pandas baseline."*
- **Required 9 Primitives**:
  The 9 required primitives are `ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, and `ts_argmin`.
- **Target File Location**: Repository root `f:\Projects\alpha_farm\benchmark_primitives.py`.
- **Verification Analysis Written**: Complete specification, naive Pandas baselines, assertion framework (1e-5 tolerance), and benchmarking code are recorded in `f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_3\analysis.md`.

---

## 2. Logic Chain

1. **Observation**: `PROJECT.md` requires a verification and performance benchmark script at `benchmark_primitives.py`.
2. **Reasoning**: A standalone benchmark script serves a dual role: (a) verifying that vectorized Numpy implementations in `AlphaPrimitives.py` produce mathematically identical results to naive Pandas reference implementations within `1e-5` tolerance, and (b) measuring execution time (ms) and speedup factors ($x$).
3. **Observation**: Naive Pandas rolling operations (`.rolling().apply()`, `.rolling().mean()`, `.rolling().corr()`) provide standard, unambiguous baseline calculations.
4. **Reasoning**: By defining pure naive Pandas reference functions (`naive_ts_mean`, `naive_ts_rank`, etc.), `benchmark_primitives.py` can compare outputs element-by-element using `np.allclose(..., rtol=1e-5, atol=1e-5, equal_nan=True)` to confirm numerical equivalence.
5. **Observation**: Backtest execution speeds depend heavily on time-series primitive performance across datasets of $N \ge 10,000$ rows.
6. **Reasoning**: Benchmarking using `time.perf_counter()` over $K=5$ iterations with synthetic time series data ($N=10,000$, window $d=20$) provides reliable timing in milliseconds (`ms`) and speedup multipliers ($x$).

---

## 3. Caveats

- **Pre-Implementation Execution**: `core_engine/AlphaPrimitives.py` has not yet been implemented by the implementer agent. `benchmark_primitives.py` contains a safe import try/except block so it can run gracefully in mock mode or full benchmark mode once `AlphaPrimitives.py` is written.
- **Population vs Sample Standard Deviation**: `ts_zscore` baseline assumes population standard deviation (`ddof=0`) to match typical vectorized Numpy array standard deviation (`np.std(axis=-1, ddof=0)`). If `AlphaPrimitives.py` uses `ddof=1`, the baseline parameter must be updated accordingly.

---

## 4. Conclusion

The architectural design for `benchmark_primitives.py` is fully specified and documented in `analysis.md`. It provides exact naive Pandas baselines for all 9 primitives, an assertion framework enforcing `1e-5` tolerance with `equal_nan=True`, and a structured performance benchmarking suite measuring execution time (ms) and speedup multiplier (x).

---

## 5. Verification Method

To independently verify this design report:
1. Inspect `f:\Projects\alpha_farm\.agents\teamwork_preview_explorer_m2_3\analysis.md` for the full proposed script implementation and baseline specifications.
2. Inspect `f:\Projects\alpha_farm\PROJECT.md` lines 16 and 29 to verify alignment with project milestone requirements.
3. Once `benchmark_primitives.py` and `core_engine/AlphaPrimitives.py` are written by the implementer agent, verify execution by running:
   ```bash
   python benchmark_primitives.py --size 10000 --window 20
   ```
   *Pass Condition*: Script prints tabular results with `PASS` for all 9 primitives and exits with code 0.
