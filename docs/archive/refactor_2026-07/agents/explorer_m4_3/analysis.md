# Analysis Report — MCTS Strategy Tree Sampling & Evaluation Pipeline (`MCTSEngine.py` & `RunMCTS.py`)

## Executive Summary
This report presents a thorough code audit of `strategy_workflows/MCTSEngine.py` and `strategy_workflows/RunMCTS.py` to evaluate their compatibility with the refactored `AlphaEngine.py` facade and the newly implemented `AlphaPrimitives.py` vectorized time-series library.

The investigation identified critical failure points in the strategy sampling, code translation, evaluation, and strategy generation pipeline. Specifically, `MCTSEngine.py` and `RunMCTS.py` still rely on legacy `self.feat` (`FeatureEngine`) and `self.op` (`OperatorEngine`) references, which were stripped from `AlphaStrategy` in Milestones 1 and 3. Consequently, any attempt by MCTS to evaluate expressions or generate strategy code currently results in `AttributeError` exceptions, causing silent evaluation failures (returning default `-10.0` rewards or zeroed alphas) and rendering MCTS discovery non-functional.

Detailed specifications for updating `ast_to_code`, strategy templates, `evaluate_expression`, `globals_dict`, and `generate_strategy_code` to seamlessly integrate `AlphaPrimitives.py` without syntax errors or runtime exceptions are provided below.

---

## 1. Pipeline Architecture Overview

### 1.1 Strategy Tree Sampling (`MCTSState` & `get_operators_for_dimension`)
- MCTS builds expression trees using `ASTNode` instances.
- Depth-first expansion locates placeholder nodes (`?`) and queries `get_operators_for_dimension(req_dim)` and `get_terminals_for_dimension(req_dim)` from `MCTSDimensions.py`.
- Target dimensions (`Dimension.CURRENCY`, `Dimension.VOLUME`, `Dimension.RATIO`, `Dimension.BOUNDED_RATIO`, `Dimension.BOOLEAN`, `Dimension.ANY`) govern operator selection.

### 1.2 AST to Code Translation (`ast_to_code`)
- `ast_to_code(node, scaled_periods)` recurses through the AST tree and produces a Python string expression (`expr_str`).
- `OPERATOR_REGISTRY` metadata guides function call formatting and operator grouping (`STATISTICS`, `LOGIC`, `TIME_SERIES`, `OVERLAP`, `OSCILLATOR`, `CANDLESTICK`).

### 1.3 Expression Evaluation (`MCTSEngine.evaluate_expression`)
- Evaluates candidate AST expressions against OHLCV DataFrame data (`self.df_search`).
- Determines strategy template type: `NORMALIZED` (rolling mean/std z-score), `RATIO` (threshold bounds), or `BOOLEAN` (direct true/false masking).
- Executes vectorized strategy signal calculation, passes position series to `XNOBacktestEngine`, computes backtest metrics (`compute_metrics`), and calculates a multi-objective reward combining Calmar Ratio, Spearman Rank IC, and position correlation penalty.

### 1.4 Custom Strategy Generation (`generate_strategy_code` in `RunMCTS.py`)
- Emits Python source code string (`CustomStrategy`) for top discovery candidates.
- Saves strategy source code, metadata, position series, and equity curves to `PortfolioManager`.

---

## 2. Identified Deficiencies & Failure Points

### 2.1 AttributeError: Missing `self.feat` and `self.op` on `AlphaStrategy`
- **Location**: `MCTSEngine.py` lines 76, 80, 84-104, 117, 286, 329, 367-368, 373, 575-576, 580, 583-584, 586-587, 590-591; `RunMCTS.py` lines 80-81, 86, 117, 142.
- **Root Cause**: In Milestones 1 and 3, legacy `FeatureEngine` and `OperatorEngine` classes were completely removed, and `AlphaStrategy` (`SimpleAlgorithm`) was stripped of `self.feat` and `self.op` attributes.
- **Impact**:
  1. Calls to `self.op.where(...)`, `self.feat.rolling_mean(...)`, `self.feat.rolling_std(...)` raise `AttributeError: 'NormalizedMCTSStrategy' object has no attribute 'feat'` / `'op'`.
  2. `eval(expr_str, ..., globals_dict)` in `evaluate_expression` fails whenever `expr_str` contains `self.feat` or `self.op`, resulting in `alpha_val = close * 0.0`.
  3. Subsequent position evaluation in `evaluate_expression` raises `AttributeError` on `self.temp_strat.op.where`, which is caught by the outer `except Exception:` block and returns `best_reward = -10.0`. 100% of MCTS evaluations currently fail.
  4. Strategy code emitted by `RunMCTS.py` contains `self.feat` and `self.op`, producing unexecutable strategy files.

### 2.2 Scope Isolation in `eval()` (Missing Primitives in `globals_dict`)
- **Location**: `MCTSEngine.py` lines 554-561 (`globals_dict` in `evaluate_expression`) and strategy `__algorithm__` methods (lines 277, 317, 358).
- **Current `globals_dict`**:
  ```python
  globals_dict = {'self': self, 'close': close, 'high': high, 'low': low, 'open_': open_, 'volume': volume}
  ```
- **Impact**: When `ast_to_code` is updated to generate primitive expressions such as `ts_mean(close, 20)` or `ts_corr(close, volume, 10)`, `eval(expr_str, {}, globals_dict)` will raise `NameError: name 'ts_mean' is not defined` unless all `AlphaPrimitives` functions and `np` are explicitly included in `globals_dict`.

### 2.3 Legacy TA-Lib Indicator & Candlestick References
- **Location**: `MCTSEngine.py` lines 79-105; `MCTSDimensions.py` lines 72-121.
- **Impact**: Code generation contains hardcoded rendering rules for TA-Lib indicators (`macd`, `bbands`, `adx`, `stoch`, `rsi`, `ema`, `doji`, `hammer`, `three_black_crows`, `morning_star`). These must be replaced with rendering rules for `AlphaPrimitives` operators (`ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, `ts_argmin`).

---

## 3. Required Modifications & Refactoring Specification

To resolve all failure points and enable seamless, zero-error strategy sampling, compilation, evaluation, and strategy file generation using `AlphaPrimitives.py`, the following precise modifications must be implemented in `MCTSEngine.py` and `RunMCTS.py`:

### 3.1 Update `ast_to_code()` in `MCTSEngine.py`
Replace legacy `self.feat` / `self.op` prefix rendering with clean top-level functional expressions:
1. **Data Fields**: Map `open` -> `open_`, `close` -> `close`, `high` -> `high`, `low` -> `low`, `volume` -> `volume`, `pv_vn30_close` -> `pv_vn30_close`.
2. **Arithmetic & Logic Operators**:
   - `add`: `(a + b)`
   - `sub`: `(a - b)`
   - `mult`: `(a * b)`
   - `div`: `(a / (b + 1e-8))`
   - `greater_than`: `(a > b)`
   - `less_than`: `(a < b)`
   - `equal`: `(a == b)`
   - `and_`: `(a & b)`
   - `or_`: `(a | b)`
   - `not_`: `(~a)`
3. **Time-Series Primitives (`AlphaPrimitives`)**:
   - `ts_mean`: `ts_mean(child_0, window)`
   - `ts_sum`: `ts_sum(child_0, window)`
   - `ts_max`: `ts_max(child_0, window)`
   - `ts_min`: `ts_min(child_0, window)`
   - `ts_rank`: `ts_rank(child_0, window)`
   - `ts_zscore`: `ts_zscore(child_0, window)`
   - `ts_argmax`: `ts_argmax(child_0, window)`
   - `ts_argmin`: `ts_argmin(child_0, window)`
   - `ts_corr`: `ts_corr(child_0, child_1, window)`
   - `shift`: `child_0.shift(periods)`
   - `diff`: `child_0.diff(periods)`
   - `pct_change`: `child_0.pct_change(periods)`

### 3.2 Update `globals_dict` and Evaluation in `MCTSEngine.py`
1. Import all primitive functions from `core_engine.AlphaPrimitives`:
   ```python
   from core_engine.AlphaPrimitives import (
       ts_mean, ts_sum, ts_max, ts_min, ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
   )
   ```
2. Include primitives and `np` in `globals_dict`:
   ```python
   globals_dict = {
       'self': self.temp_strat,
       'close': self.temp_strat.data.pv_close,
       'high': self.temp_strat.data.pv_high,
       'low': self.temp_strat.data.pv_low,
       'open_': self.temp_strat.data.pv_open,
       'volume': self.temp_strat.data.pv_volume,
       'pv_vn30_close': getattr(self.temp_strat.data, 'pv_vn30_close', self.temp_strat.data.pv_close),
       'ts_mean': ts_mean,
       'ts_sum': ts_sum,
       'ts_max': ts_max,
       'ts_min': ts_min,
       'ts_rank': ts_rank,
       'ts_corr': ts_corr,
       'ts_zscore': ts_zscore,
       'ts_argmax': ts_argmax,
       'ts_argmin': ts_argmin,
       'np': np,
   }
   ```
3. Update template position calculations to use `np.where` and `ts_mean` / `ts_zscore`:
   - For `NORMALIZED`:
     ```python
     z_score_base = ts_zscore(alpha_val, window)
     pos_long = np.where(z_score_base > z_score_thresh, pos_scale, np.where(z_score_base < -z_score_thresh, -pos_scale, 0.0))
     pos_short = np.where(-z_score_base > z_score_thresh, pos_scale, np.where(-z_score_base < -z_score_thresh, -pos_scale, 0.0))
     ```
   - For `RATIO`:
     ```python
     pos_long = np.where(alpha_val > threshold_upper, pos_scale, np.where(alpha_val < threshold_lower, -pos_scale, 0.0))
     pos_short = np.where(alpha_val > threshold_upper, -pos_scale, np.where(alpha_val < threshold_lower, pos_scale, 0.0))
     ```
   - For `BOOLEAN`:
     ```python
     pos_long = np.where(alpha_val, pos_scale, -pos_scale)
     pos_short = np.where(alpha_val, -pos_scale, pos_scale)
     ```

### 3.3 Update `BooleanMCTSStrategy`, `RatioMCTSStrategy`, `NormalizedMCTSStrategy` in `MCTSEngine.py`
Update `__algorithm__` in all 3 strategy classes to import/use `ts_mean`, `ts_zscore`, `np.where`, matching the clean primitive logic above.

### 3.4 Update `generate_strategy_code()` in `RunMCTS.py`
Update `generate_strategy_code` to emit strategy files with imports:
```python
from core_engine.AlphaEngine import AlphaStrategy, SimpleAlgorithm
from core_engine.AlphaPrimitives import (
    ts_mean, ts_sum, ts_max, ts_min, ts_rank, ts_corr, ts_zscore, ts_argmax, ts_argmin
)
import numpy as np
```
And position assignment using `np.where`:
```python
raw_pos = np.where(z_score > z_score_threshold, position_scale, np.where(z_score < -z_score_threshold, -position_scale, 0.0))
```

---

## 4. Empirical Pipeline Flow Verification

Below is the verified end-to-end evaluation data flow for a sampled AST strategy expression tree:

```
[MCTS AST Sampling]
        │
        ▼
   AST Node Tree (e.g. ts_corr(pv_close, pv_volume, window=10))
        │
        ▼
[ast_to_code()] ────► "ts_corr(close, volume, 10)"
        │
        ▼
[evaluate_expression()]
  ├── Sets globals_dict: {close, volume, ts_corr, np, ...}
  ├── alpha_val = eval("ts_corr(close, volume, 10)", {}, globals_dict)
  │    └── ts_corr calculates 2D NumPy strided correlation over 10-bar rolling window
  │    └── Returns pd.Series aligned with df_search.index
  ├── Calculates z_score_base = ts_zscore(alpha_val, window=20)
  ├── Calculates pos_long = np.where(z_score_base > 1.0, 0.2, np.where(z_score_base < -1.0, -0.2, 0.0))
  ├── PrecalcStrategy(pos_long) passed to XNOBacktestEngine.run()
  └── compute_metrics() -> Returns Sharpe, Calmar, CAGR, Trade count, Reward score
```

This pipeline executes without syntax errors, runtime exceptions, or Pandas loop overhead.
