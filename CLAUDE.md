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
- `token.txt` is **tracked in git** despite `.gitignore`. Never stage it.

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

## Pipeline architecture

1. **Generate** (`strategy_workflows/GenerateStrategies.py` + `utilities/Prompts.py`)
   - The LLM returns JSON with a `macro_blueprint`, an expression with `?` slots, e.g. `ts_zscore(sub(?, ts_mean(?)))`.
   - `SemanticCompiler` parses it with Python `ast`, maps hallucinated names through `HALLUCINATION_MAP`, and type-checks dimensions.
   - On a compile error the LLM is asked to self-correct.
   - Valid ideas are saved to `results/ideas/<name>_<tf>.json`.
2. **MCTS** (`strategy_workflows/RunMCTS.py`)
   - Runs one process per timeframe (`TIMEFRAMES`, 1m–60m).
   - Each process compiles the idea files for its timeframe, then calls `MCTSEngine.run_search_from_blueprint`.
   - Processed files are moved to `results/ideas/processed/`, including on error, so failures are easy to miss.
3. **Search space** (`strategy_workflows/MCTSDimensions.py`)
   - Every operator declares input and output `Dimension`s (CURRENCY, VOLUME, RATIO, BOOLEAN, ANY). MCTS only fills a slot with a dimension-compatible node.
   - The dimension of the root picks the position template in `MCTSEngine` (NORMALIZED / RATIO / BOOLEAN).
4. **Scoring** (`MCTSEngine.evaluate_expression`)
   - `eval()`s the generated expression with the `ts_*` functions from `core_engine/AlphaPrimitives.py`.
   - Backtests both directions and keeps the better one.
   - Reward = `(0.6·S_calmar + 0.4·S_IC)·(1 − max position corr with portfolio)`, hard −10 if Calmar < 1.1 or fewer than 15 trades.
   - Selection is UCT on **max** reward, not mean.
5. **Validation** (`strategy_workflows/HMMValidation.py`)
   - Fits a 3-state Gaussian HMM, then generates paths by Markov-chain block bootstrap (20-bar blocks).
   - The 3 tiers: ruin rate, Kelly + cost coverage, and CAGR/Sharpe vs savings rate and buy-and-hold.
   - Synthetic paths are cached in `data/MCdata/synthetic_data.pkl` (~13 GB). `--retrain-hmm` rebuilds it.
6. **Portfolio** (`PortfolioManager`)
   - Writes `results/portfolio_summary.json` plus per-strategy `.py`, equity and positions CSVs.
   - `RunMCTS` passes `force_add=True`, and correlation rejection is commented out, so criteria are not enforced.

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

## Known state after the XNOQuant decoupling (commit `3bdc8fd`)

The project was originally built for the XNOQuant competition sandbox (`XnoEngine` with TA-Lib `self.feat`/`self.op`, `RestrictedSeries`, Playwright submission). The refactor replaced indicators with `ts_*` primitives but left the pipeline broken end to end. The unit tests do not exercise these paths.

1. **LLM prompt:** `utilities/Prompts.py` still lists TA-Lib operators (`ema`, `macd_line`, `zscore`, …). The compiler rejects all of the prompt's own few-shot examples.
2. **MCTS expansion:** `get_terminals_for_dimension` references the removed `OperatorGroup.CANDLESTICK`, so expansion raises `AttributeError` for BOOLEAN/ANY slots.
3. **Scoring:** `evaluate_expression` passes `np.where(...)` arrays (not Series) to the backtest. The `.shift` error is swallowed, so every candidate gets reward −10.
4. **Exported code:** `RunMCTS.generate_strategy_code` emits code using `self.feat`/`self.op` and does not import `ts_*`, so it cannot run.
5. **Random windows:** `ast_to_code` picks window lengths with `random.choice` on every render, so one MCTS node maps to many different formulas.
6. **Missing operators:** there are no lag/delta operators (`ts_delay`, `ts_delta`).

Other leftovers from the refactor:
- `core_engine/PlatformEmulator.py`, `RestrictedSeries.py` and `strategy_workflows/SubmitStrategies.py` are one-line "DELETED" stubs.
- First-generation (TA-Lib) strategy artifacts were removed from `results/pushed/` in that commit. Recover them with `git checkout eec5f06 -- results/pushed`.
- `results/portfolio_summary.json` and `3tier_results.csv` contain only first-generation strategies.

## Thesis documents

- `docs/proposal/thesis_proposal/Thesis_Proposal.tex` follows the department template in `docs/proposal/Sample_Thesis_Tex_format_2026/` (IU, Department of Mathematics).
- Build: `~/.local/bin/tectonic.exe Thesis_Proposal.tex`. Use XeTeX-safe fonts; `\mathbbm` breaks xdvipdfmx.
- Figures are regenerated from repo data with `python docs/proposal/thesis_proposal/make_figures.py`.
- Bibliography entries were verified against publisher or arXiv pages. Do not add unverified citations.
- `docs/ARCH.md` describes the architecture as the code is today (Vietnamese); update it in the same change when code behaviour changes. `docs/archive/` is history (XNOQuant era): never treat it as current.
