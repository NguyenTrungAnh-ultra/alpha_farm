# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Alpha Farm discovers **directional trading signals** (long/short/flat) for the VN30 index futures contract VN30F1M. An LLM proposes the structure of a strategy, MCTS searches for the complete formula, and the formula is scored by a futures backtest and filtered by an HMM-based robustness test. The project also serves as a bachelor's thesis, so methodological correctness matters as much as code. README, logs and most comments are in Vietnamese.

Current plan, status and open decisions: `docs/ROADMAP.md` (Vietnamese). Update it when a task finishes or the user decides something.

Code changes go to the `coder` agent (`.claude/agents/coder.md`, Sonnet, medium effort). The main session writes the brief, then reviews the diff and re-runs the tests before reporting done.

## Environment

- Use the **`.venv`** interpreter (Python 3.12, managed with `uv`). It is synced to `requirements.txt`, compiled from `requirements.in`. Add a dependency to `requirements.in`, recompile, then `uv pip sync`; never `uv pip install` ad hoc, since the next sync removes it.
- The `venv/` directory is empty.
- System Python 3.14 has no `hmmlearn` wheel. On 3.14, `tests/test_hmm_validation.py` is silently skipped and `HMMValidation` cannot be imported.
- The only LLM provider is local Ollama; models come from `Modelfile` (qwen3.5). Do not add cloud LLM clients or credential files.

## Commands

```bash
.venv/Scripts/python.exe main.py                       # interactive menu
.venv/Scripts/python.exe main.py generate --n_strategies 20 --model ollama-local   # LLM -> blueprints
.venv/Scripts/python.exe main.py mcts --iterations 50000 --patience 5000 [--retrain-hmm]
.venv/Scripts/python.exe main.py full ...              # generate then mcts

.venv/Scripts/python.exe -m pytest                     # all tests (pytest.ini: testpaths=tests, pythonpath=.)
.venv/Scripts/python.exe -m pytest tests/test_alpha_primitives.py::test_all_primitives_pandas_equivalence
.venv/Scripts/python.exe -m pytest -m "not slow"       # markers: slow, core, hardware (--strict-markers)
.venv/Scripts/python.exe benchmark_primitives.py       # AlphaPrimitives vs pandas: speed + equivalence
```

`--model` accepts: `ollama-local`, `ollama-9b`.

As of 2026-10-28, the suite in `.venv` gives 59 passed and 1 failed. The failure is `test_core_engine.py::test_alpha_data_proxy`, an identity check (`is`) on a copied Series.

## Pipeline gotchas

Stages (generate → MCTS → scoring → HMM validation → portfolio) are described in `docs/ARCH.md`.

- `RunMCTS` moves idea files to `results/ideas/processed/` even on error, so failures are easy to miss.
- MCTS selection is UCT on **max** reward, not mean.
- `RunMCTS` passes `force_add=True`, and correlation rejection is commented out, so portfolio criteria are not enforced.
- HMM synthetic paths are cached per (timeframe, data fingerprint) in `data/MCdata/synthetic/`. The legacy `data/MCdata/synthetic_data.pkl` (~13 GB) is never read; until `--retrain-hmm` builds keyed files, `main.py mcts` skips the HMM step with a message.

## Core engine conventions

- **All thresholds and contract specs live in `utilities/AppConfig.py`**: reward weights, tier thresholds, multiplier 100,000 VND/point, fee 6,000 VND/contract/side, margin 28.5% / maintenance 20%, `BACKTEST_START/END`.
- **Data:** `load_data(tf)` reads `data/DNSE_VN30F_{tf}.csv` filtered to `BACKTEST_START..BACKTEST_END`. `'60m'` maps to the `1H` file. Data run 2018-08 to 2025-12, but only 2020–2024 is used, so there is no out-of-sample split yet.
- **Window scaling:** periods are defined at 10m (`BASELINE_TF_MINUTES`) and scaled per timeframe (`BASE_PERIODS`, `BASE_WINDOW_SEARCH`).
- **`AlphaBacktestEngine.run(strategy, df)`:**
  - Calls `strategy.run_algorithm(df)` and expects a **`pd.Series`** of target positions, because it calls `.shift(1)`.
  - A signal at bar t executes at bar t+1.
  - Contract count is fixed from initial capital and the first price.
  - A margin call flattens all positions and freezes equity.
- **Annualisation:** everything goes through `CalculateMetrics.compute_metrics`. CAGR uses elapsed calendar time (/365.25 days); Sharpe/Sortino/vol use daily returns with sqrt(252). Never count trading days for years: the 1m–30m files miss 126 sessions in 2023–2024 that the 1H file has.
- **Data injection:** `MCTSEngine(data=...)`, `precompute_hmm_synthetic_data({tf: df})` and `process_timeframe(tf, data, ...)` use only the frame they are given; only `run_mcts_pipeline` / no-`data` defaults call `load_data`.

## Known state after the XNOQuant decoupling (commit `c6b1f03`)

The project was originally built for the XNOQuant competition sandbox (`XnoEngine` with TA-Lib `self.feat`/`self.op`, `RestrictedSeries`, Playwright submission). The pipeline now runs end to end on `ts_*` blueprints (`tests/test_mcts_pipeline.py`). Still open:

- No lag/delta operators (`ts_delay`, `ts_delta`). Operators in `UNIMPLEMENTED_OPERATORS` (`crossed*`, `rising`, `falling`, `between`) are never proposed, and a blueprint using one is rejected.
- Evaluation errors still score −10. Check `MCTSEngine.error_summary()` after a run instead of trusting the leaderboard.
- `main.py mcts` / `process_timeframe` (which need the HMM cache) have not been run since the rewire.

Other leftovers from the refactor:
- First-generation (TA-Lib) strategy artifacts were removed from `results/pushed/` in that commit. Recover them with `git checkout cfeb770 -- results/pushed`.
- `results/portfolio_summary.json` and `3tier_results.csv` contain only first-generation strategies.

## Thesis documents

- Build and template notes for the proposal: `docs/proposal/CLAUDE.md`.
- Bibliography entries were verified against publisher or arXiv pages. Do not add unverified citations.
- `docs/ARCH.md` describes the architecture as the code is today (Vietnamese); update it in the same change when code behaviour changes. `docs/archive/` is history (XNOQuant era): never treat it as current.
