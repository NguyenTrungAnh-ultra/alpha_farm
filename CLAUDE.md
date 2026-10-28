# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Alpha Farm discovers **directional trading signals** (long/short/flat) for the VN30 index futures contract VN30F1M. An LLM proposes the structure of a strategy, MCTS searches for the complete formula, and the formula is scored by a futures backtest and filtered by an HMM-based robustness test. The project also serves as a bachelor's thesis, so methodological correctness matters as much as code. README, logs and most comments are in Vietnamese.

Current plan, status and open decisions: `docs/ROADMAP.md` (Vietnamese). Update it when a task finishes or the user decides something.

## Environment

- Use the **`.venv`** interpreter (Python 3.12, managed with `uv`). It has `hmmlearn`.
- The `venv/` directory is empty.
- System Python 3.14 has no `hmmlearn` wheel. On 3.14, `tests/test_hmm_validation.py` is silently skipped and `HMMValidation` cannot be imported.
- LLM credentials are read from `token.txt` (DeepSeek) and `cookies.txt` (Gemini) in the repo root. Ollama models come from `Modelfile` (qwen3.5).
- `token.txt` and `api.txt` hold credentials and are gitignored. Never stage them.

## Commands

```bash
.venv/Scripts/python.exe main.py                       # interactive menu
.venv/Scripts/python.exe main.py generate --n_strategies 20 --model deepseek-thinking   # LLM -> blueprints
.venv/Scripts/python.exe main.py mcts --iterations 50000 --patience 5000 [--retrain-hmm]
.venv/Scripts/python.exe main.py full ...              # generate then mcts

.venv/Scripts/python.exe -m pytest                     # all tests (pytest.ini: testpaths=tests, pythonpath=.)
.venv/Scripts/python.exe -m pytest tests/test_alpha_primitives.py::test_all_primitives_pandas_equivalence
.venv/Scripts/python.exe -m pytest -m "not slow"       # markers: slow, core, hardware (--strict-markers)
.venv/Scripts/python.exe benchmark_primitives.py       # AlphaPrimitives vs pandas: speed + equivalence
```

`--model` accepts: `deepseek-thinking`, `ollama-local`, `ollama-9b`, `flash`, `pro`, `thinking`.

As of 2026-10-01, the suite in `.venv` gives 37 passed and 1 failed. The failure is `test_core_engine.py::test_alpha_data_proxy`, an identity check (`is`) on a copied Series.

## Pipeline gotchas

Stages (generate → MCTS → scoring → HMM validation → portfolio) are described in `docs/ARCH.md`.

- `RunMCTS` moves idea files to `results/ideas/processed/` even on error, so failures are easy to miss.
- MCTS selection is UCT on **max** reward, not mean.
- `RunMCTS` passes `force_add=True`, and correlation rejection is commented out, so portfolio criteria are not enforced.
- HMM synthetic paths are cached in `data/MCdata/synthetic_data.pkl` (~13 GB); `--retrain-hmm` rebuilds it.

## Core engine conventions

- **All thresholds and contract specs live in `utilities/AppConfig.py`**: reward weights, tier thresholds, multiplier 100,000 VND/point, fee 6,000 VND/contract/side, margin 28.5% / maintenance 20%, `BACKTEST_START/END`.
- **Data:** `load_data(tf)` reads `data/DNSE_VN30F_{tf}.csv` filtered to `BACKTEST_START..BACKTEST_END`. `'60m'` maps to the `1H` file. Data run 2018-08 to 2025-12, but only 2020–2024 is used, so there is no out-of-sample split yet.
- **Window scaling:** periods are defined at 10m (`BASELINE_TF_MINUTES`) and scaled per timeframe (`BASE_PERIODS`, `BASE_WINDOW_SEARCH`).
- **`AlphaBacktestEngine.run(strategy, df)`:**
  - Calls `strategy.run_algorithm(df)` and expects a **`pd.Series`** of target positions, because it calls `.shift(1)`.
  - A signal at bar t executes at bar t+1.
  - Contract count is fixed from initial capital and the first price.
  - A margin call flattens all positions and freezes equity.
- **Two different annualisations:**
  - `CalculateMetrics.compute_metrics` resamples to daily and uses 252 (correct).
  - `HMMValidation.calculate_metrics_for_result` infers years from the bar count with constants 4800/1200. This is wrong for most timeframes: buy-and-hold CAGR comes out 0.76% on 1m vs 8.9% true.

## Known state after the XNOQuant decoupling (commit `c6b1f03`)

The project was originally built for the XNOQuant competition sandbox (`XnoEngine` with TA-Lib `self.feat`/`self.op`, `RestrictedSeries`, Playwright submission). The refactor replaced indicators with `ts_*` primitives but left the pipeline broken end to end. The unit tests do not exercise these paths.

1. **LLM prompt:** `utilities/Prompts.py` still lists TA-Lib operators (`ema`, `macd_line`, `zscore`, …). The compiler rejects all of the prompt's own few-shot examples.
2. **MCTS expansion:** `get_terminals_for_dimension` references the removed `OperatorGroup.CANDLESTICK`, so expansion raises `AttributeError` for BOOLEAN/ANY slots.
3. **Scoring:** `evaluate_expression` passes `np.where(...)` arrays (not Series) to the backtest. The `.shift` error is swallowed, so every candidate gets reward −10.
4. **Exported code:** `RunMCTS.generate_strategy_code` emits code using `self.feat`/`self.op` and does not import `ts_*`, so it cannot run.
5. **Random windows:** `ast_to_code` picks window lengths with `random.choice` on every render, so one MCTS node maps to many different formulas.
6. **Missing operators:** there are no lag/delta operators (`ts_delay`, `ts_delta`).

Other leftovers from the refactor:
- First-generation (TA-Lib) strategy artifacts were removed from `results/pushed/` in that commit. Recover them with `git checkout cfeb770 -- results/pushed`.
- `results/portfolio_summary.json` and `3tier_results.csv` contain only first-generation strategies.

## Thesis documents

- Build and template notes for the proposal: `docs/proposal/CLAUDE.md`.
- Bibliography entries were verified against publisher or arXiv pages. Do not add unverified citations.
- `docs/ARCH.md` describes the architecture as the code is today (Vietnamese); update it in the same change when code behaviour changes. `docs/archive/` is history (XNOQuant era): never treat it as current.
