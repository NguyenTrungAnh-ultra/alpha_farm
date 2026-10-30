# CLAUDE.md

Alpha Farm discovers directional signals (long/short/flat) for VN30F1M futures: an LLM proposes a strategy skeleton (blueprint), MCTS fills it in, a futures backtest scores it; the HMM bootstrap only describes risk (rejects nothing). It is a bachelor's thesis, so methodology matters as much as code. Docs, logs and most comments are Vietnamese.

## Workflow
- Docs vault, MOC `docs/START_HERE.md`: `PLAN.md` (backlog, open questions, debts), `DECISIONS.md` (decision log), `RESULTS.md` (numbers the thesis uses), `design/` (living docs), `log/` (journal). `docs/archive/` is XNOQuant-era history, never current.
- `docs/design/ARCH.md` describes the code as it is today: update it in the same change as any behaviour change. Update the matching doc in the same turn a task finishes or the user decides.
- Code goes to the `coder` agent (`.claude/agents/coder.md`); the main session writes the brief, reviews the diff and re-runs the tests before reporting.

## Environment
- Use `.venv` (Python 3.12, `uv`), synced to `requirements.txt` compiled from `requirements.in`: add deps to `.in`, recompile, `uv pip sync`; never ad-hoc `uv pip install`. `venv/` is empty.
- System Python 3.14 has no `hmmlearn` wheel: `tests/test_hmm_validation.py` skips silently and `HMMValidation` cannot be imported there.
- Only LLM provider: local Ollama (`Modelfile`, qwen3.5). No cloud LLM clients or credential files.

## Commands
```bash
.venv/Scripts/python.exe main.py [generate|mcts|full|planted|walkforward|web] ...   # no args: menu
.venv/Scripts/python.exe -m pytest -m "not slow"    # markers: slow, core, hardware (--strict-markers)
.venv/Scripts/python.exe benchmark_primitives.py    # AlphaPrimitives vs pandas: speed + equivalence
```
- `--model`: `ollama-local`, `ollama-9b`.
- Baseline 2026-10-30 (`-m "not slow"`): 287 passed, 1 failed (`test_core_engine.py::test_alpha_data_proxy`, an `is` check on a copied Series).

## Engine conventions
- Thresholds and contract specs live in `utilities/AppConfig.py`: reward weights, multiplier 100,000 VND/point, fee 6,000 VND/contract/side, margin 28.5% / maintenance 20%, `BACKTEST_START/END`.
- `load_data(tf, start=BACKTEST_START, end=BACKTEST_END)` reads `data/DNSE_VN30F_{tf}.csv` (2018-08 → 2025-12); `'60m'` maps to the `1H` file. Planted and walk-forward pass their own bounds.
- Periods are defined at 10m (`BASELINE_TF_MINUTES`) and scaled per timeframe (`BASE_PERIODS`, `BASE_WINDOW_SEARCH`).
- `AlphaBacktestEngine.run(strategy, df)`:
  - expects a `pd.Series` of target positions, since it calls `.shift(1)`; a signal at t fills at t+1;
  - contract count is fixed from initial capital and the first price;
  - a margin call flattens and freezes equity.
- Annualise only through `CalculateMetrics.compute_metrics`:
  - CAGR on calendar time (/365.25);
  - Sharpe, Sortino and vol on daily returns × √252;
  - never count trading days, because the 1m–30m files miss 126 sessions in 2023–2024.
- `MCTSEngine(data=...)`, `precompute_hmm_synthetic_data({tf: df})` and `process_timeframe(tf, data, ...)` use only the frame they are given; only the no-`data` defaults call `load_data`.

## Gotchas
- `REWARD_MODES` are "gated", "soft" and "sharpe". Thesis runs use "sharpe", but the default is "gated": pass the mode explicitly.
- MCTS selection is UCT on **max** reward. Evaluation errors score −10, so read `MCTSEngine.error_summary()` after a run instead of trusting the leaderboard.
- `RunMCTS` moves idea files to `results/ideas/processed/` even on error.
- HMM paths are cached per (timeframe, data fingerprint) in `data/MCdata/synthetic/`.
  - The legacy `synthetic_data.pkl` (~13 GB) is never read.
  - Without `--retrain-hmm`, `main.py mcts` skips the HMM step.
  - `main.py mcts` has not run since the XNOQuant decoupling (`c6b1f03`).
- There is no `ts_delay` or `ts_delta`. `UNIMPLEMENTED_OPERATORS` (`crossed*`, `rising`, `falling`, `between`) are never proposed, and a blueprint using one is rejected.
- First-generation (TA-Lib) artifacts can be restored with `git checkout cfeb770 -- results/pushed`. `results/portfolio_summary.json` and `3tier_results.csv` hold only those.

## Thesis
- Proposal build notes: `docs/proposal/CLAUDE.md`. Bibliography entries are verified against publisher or arXiv pages; add no unverified citation.
