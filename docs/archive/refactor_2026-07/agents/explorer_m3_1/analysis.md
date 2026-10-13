# Detailed Analysis: Refactoring XnoEngine.py to AlphaEngine.py

## 1. Executive Summary

This analysis details the exact refactoring of `core_engine/XnoEngine.py` into `core_engine/AlphaEngine.py` for **Milestone 3 (Refactor Engine to AlphaEngine)**.

The refactoring eliminates all legacy XNOQuant AST/bytecode sandbox wrappers (`FeatureEngine` with C-extension TA-Lib dependency, `OperatorEngine` with 30 sandbox operator wrappers, whitelist parsing, and sandbox constraints validation), while constructing `core_engine/AlphaEngine.py` as a high-performance engine that integrates `BacktestEngine` (which models VN30F futures margin, netting fees, intra-bar margin call liquidations, and 3rd-Thursday contract rollover penalties).

---

## 2. Detailed Line-by-Line Breakdown of `core_engine/XnoEngine.py`

File: `f:/Projects/alpha_farm/core_engine/XnoEngine.py` (961 lines, 40,940 bytes)

### 2.1 Imports and Module Setup (Lines 1-24)
- **Docstring (Lines 1-16)**: Describes legacy sandbox execution environment (`FeatureEngine`, `OperatorEngine`, `DataProxy`, `SimpleAlgorithm`).
- **Imports (Lines 18-23)**:
  - `import pandas as pd`
  - `import numpy as np`
  - `import talib` *(TA-Lib C-library dependency — to be REMOVED)*
  - `import logging`
  - `import os` *(Used for whitelist file lookup — to be REMOVED)*
  - `import re` *(Used for regex whitelist matching — to be REMOVED)*
- **Logger (Line 24)**: `logger = logging.getLogger("core_engine.XnoEngine")` (to be updated to `"core_engine.AlphaEngine"`).

### 2.2 Top-Level Legacy Whitelist Logic (Lines 26-106)
- **`_load_feature_whitelist()` (Lines 26-77)**: Parses `feature.txt` or `docs/feature.txt` using regex to find allowed `self.feat.*` methods; falls back to a hardcoded set of 74 function name strings. *(To be REMOVED)*
- **`TALIB_NAME_MAPPING` (Lines 79-105)**: Dictionary mapping 25 snake_case candlestick pattern names (e.g. `piercing_pattern`, `engulfing_pattern`, `harami_pattern`) to TA-Lib C-library function names (e.g. `CDLPIERCING`). *(To be REMOVED)*

### 2.3 `FeatureEngine` Class (Lines 107-490)
Mocks `self.feat.*` providing TA-Lib indicators, custom rolling/statistical functions, and parameter normalization.
- **`__init__` & `_wrap_normalize_params` (Lines 114-173)**: Binds parameter normalizers to inspect function signatures and map `timeperiod`/`period` to `window` and drop unrecognized kwargs.
- **Helpers `_unwrap`, `_wrap` (Lines 174-180)**: Extracts `_data` attribute from legacy `RestrictedSeries` objects.
- **Custom Rolling Methods (Lines 182-290)**:
  - `rolling_mean`, `rolling_max`, `rolling_min`, `rolling_std`, `rolling_sum`, `rolling_prod`, `rolling_rank`, `rolling_percentile_rank`, `rolling_median`, `rolling_quantile`, `rolling_correlation`, `rolling_covariance`, `rolling_zscore`, `rolling_mad`, `rolling_argmax`, `rolling_argmin`.
- **Custom Statistical & Price Indicators (Lines 292-336)**:
  - `zscore`, `price_z`, `volume_z`, `returns`, `log_returns`, `donchian_upper`, `donchian_lower`, `hlc3`, `ohlc4`.
- **Volume Weighted Functions (Lines 338-366)**:
  - `vwap`, `rolling_vwap`, `cmf`.
- **Aliases & Dynamic Fallback (Lines 368-490)**:
  - `stddev`, `minmax`.
  - `__getattr__(self, name)`: Intercepts call, checks whitelist, converts `pd.Series` to `np.float64` array, dispatches to `talib` function, converts output arrays back to `pd.Series`. Has fallback argument adaptation.
*(Entire `FeatureEngine` class to be REMOVED)*

### 2.4 `OperatorEngine` Class (Lines 491-760)
Mocks `self.op.*` implementing 30 custom logical and causal operators.
- **Helpers `_unwrap`, `_wrap` (Lines 499-506)**
- **30 Operator Methods (Lines 508-760)**:
  1. `crossed` (L509)
  2. `crossed_above` (L529)
  3. `crossed_below` (L537)
  4. `current` (L546)
  5. `previous` (L551)
  6. `shift` (L557, checks `periods > 0`)
  7. `diff` (L565, checks `periods > 0`)
  8. `pct_change` (L573, checks `periods > 0`)
  9. `rising` (L581)
  10. `falling` (L587)
  11. `fillna` (L593, rejects `bfill`)
  12. `ffill` (L603)
  13. `abs` (L609)
  14. `clip` (L614)
  15. `isna` (L620)
  16. `notna` (L626)
  17. `isfinite` (L632)
  18. `zero_ifna` (L641)
  19. `sign` (L646)
  20. `replace` (L652)
  21. `between` (L658)
  22. `where` (L667)
  23. `value_when` (L675)
  24. `bars_since` (L692)
  25. `hold_for` (L720)
  26. `crossed_above_value` (L726)
  27. `crossed_below_value` (L733)
  28. `and_` (L740)
  29. `or_` (L748)
  30. `not_` (L756)
*(Entire `OperatorEngine` class to be REMOVED)*

### 2.5 `DataProxy` Class (Lines 761-781)
Mocks `self.data.*` providing strategy access to `pv_open`, `pv_high`, `pv_low`, `pv_close`, `pv_volume`.
- `__init__(self, df: pd.DataFrame)` (L767-776)
- `@property def index(self)` (L779-780)
*(To be RETAINED and RENAMED to `AlphaDataProxy`, with `DataProxy = AlphaDataProxy` alias)*

### 2.6 `SimpleAlgorithm` Class (Lines 782-961)
Base class for strategy execution.
- `__init__(self, **kwargs)` (L790-801)
- `_initialize(self, df: pd.DataFrame)` (L803-808): Sets up `self.data`, `self.feat`, `self.op`, `self._positions`.
- `set_positions(self, mask, position: float)` (L810-815)
- `__algorithm__(self)` (L816-817)
- `_validate_sandbox_constraints(self)` (L819-952): Inspects AST and bytecode to enforce sandbox restrictions (rejecting `__init__`, helper functions, `open`, `getattr`, `import`). *(To be REMOVED)*
- `run_algorithm(self, df: pd.DataFrame)` (L954-961)
*(To be RETAINED and RENAMED to `AlphaStrategy`, with `SimpleAlgorithm = AlphaStrategy` alias; remove `self.feat`, `self.op`, and `_validate_sandbox_constraints()`)*

---

## 3. Analysis of `core_engine/BacktestEngine.py`

File: `f:/Projects/alpha_farm/core_engine/BacktestEngine.py` (474 lines, 19,853 bytes)

### 3.1 Role and Architecture
`BacktestEngine.py` implements the core VN30F futures market backtesting simulation:
- **`TradeRecord` dataclass (Lines 33-76)**: Records trade entry/exit bars, prices, direction, contract counts, gross PnL, fees, net PnL.
- **`BacktestResult` dataclass (Lines 79-110)**: Stores `equity_curve`, `positions`, `trades`, `initial_capital`, `final_equity`, `total_fees`, `total_trades`.
- **`XNOBacktestEngine` class (Lines 112-440)**:
  - `initial_capital=1,000,000,000` VND (1 billion VND)
  - `margin_rate=0.285` (28.5% initial margin)
  - `maintenance_margin_rate=0.185` (18.5% maintenance margin)
  - `fee_per_contract=6,000` VND per side per contract
  - `multiplier=100.0` VND/index point
  - `rollover_penalty_points=1.5` index points penalty on 3rd Thursday of month
  - `run(strategy, df)`: Shifts positions by 1 bar (`positions.shift(1)`), computes bar-by-bar netting fees, contract sizing, intra-bar margin call liquidations, rollover penalties, mark-to-market equity curve, and list of completed `TradeRecord` instances.
- **`load_data()` utility (Lines 441-474)**: Utility for loading historical VN30F futures data.

### 3.2 Integration with `AlphaEngine`
`AlphaEngine.py` will import `XNOBacktestEngine`, `BacktestResult`, `TradeRecord`, and `load_data` directly from `core_engine.BacktestEngine`. `AlphaEngine` acts as a facade wrapping `XNOBacktestEngine` to execute strategy backtests and evaluate metrics via `CalculateMetrics.compute_metrics()`.

---

## 4. Complete Inventory: Items to Remove vs Retain/Rename

| Component | Category | Action | Rationale |
|---|---|---|---|
| `import talib` | Import | **REMOVE** | Eliminates TA-Lib C-library dependency. |
| `import os`, `import re` | Import | **REMOVE** | Whitelist file loading is abolished. |
| `_load_feature_whitelist()` | Function | **REMOVE** | Feature whitelist checks are abolished. |
| `TALIB_NAME_MAPPING` | Constant | **REMOVE** | Indicator pattern name mappings no longer needed. |
| `FeatureEngine` | Class | **REMOVE** | Superseded by `AlphaPrimitives.py` & Pandas/Numpy operations. |
| `OperatorEngine` | Class | **REMOVE** | Superseded by native Python comparison and arithmetic operators. |
| `_validate_sandbox_constraints()` | Method | **REMOVE** | AST parsing and bytecode inspection overhead eliminated. |
| `DataProxy` | Class | **RETAIN & RENAME** | Rename to `AlphaDataProxy`; retain `DataProxy = AlphaDataProxy` alias. |
| `SimpleAlgorithm` | Class | **RETAIN & RENAME** | Rename to `AlphaStrategy`; retain `SimpleAlgorithm = AlphaStrategy` alias. Strip `self.feat` & `self.op`. |
| `XnoEngine` | Class/File | **RENAME & REDESIGN**| Rename `XnoEngine.py` -> `AlphaEngine.py`. Introduce `AlphaEngine` facade class wrapping `XNOBacktestEngine`. |
| `BacktestEngine.py` | Module | **RETAIN & INTEGRATE**| Keep `core_engine/BacktestEngine.py` unchanged. Import and delegate from `AlphaEngine`. |

---

## 5. Step-by-Step Refactoring Plan for `core_engine/AlphaEngine.py`

### Step 1: File Creation / Renaming
Rename/create `core_engine/AlphaEngine.py` to replace `core_engine/XnoEngine.py`.

### Step 2: Clean Header & Imports
```python
"""
AlphaEngine
===========
Core backtesting engine facade and strategy base environment for Alpha Farm.
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

from core_engine.BacktestEngine import (
    XNOBacktestEngine,
    BacktestResult,
    TradeRecord,
    load_data,
)
from core_engine.CalculateMetrics import compute_metrics

logger = logging.getLogger("core_engine.AlphaEngine")
```

### Step 3: Define `AlphaDataProxy` (and `DataProxy` alias)
```python
class AlphaDataProxy:
    """
    Provides strategy with direct access to Vietnam Futures price and volume data fields.
    """
    def __init__(self, df: pd.DataFrame):
        self._df = df
        self.pv_open = df['Open']
        self.pv_high = df['High']
        self.pv_low = df['Low']
        self.pv_close = df['Close']
        self.pv_volume = df['Volume'].fillna(0.0) if 'Volume' in df.columns else pd.Series(0.0, index=df.index)

    @property
    def index(self):
        return self._df.index


DataProxy = AlphaDataProxy  # Alias for backward compatibility
```

### Step 4: Define `AlphaStrategy` (and `SimpleAlgorithm` alias)
```python
class AlphaStrategy:
    """
    Base class for user-defined strategy execution in AlphaEngine.
    """
    def __init__(self, **kwargs):
        self.data: Optional[AlphaDataProxy] = None
        self._positions: Optional[pd.Series] = None
        self.params: dict = kwargs.copy()
        for k, v in kwargs.items():
            setattr(self, k, v)

    def _initialize(self, df: pd.DataFrame):
        self.data = AlphaDataProxy(df)
        self._positions = pd.Series(0.0, index=df.index)

    def set_positions(self, mask, position: float):
        if hasattr(mask, '_data'):
            mask = mask._data
        self._positions.loc[mask.fillna(False).astype(bool)] = position

    def __algorithm__(self):
        raise NotImplementedError("Subclass must implement __algorithm__()")

    def run_algorithm(self, df: pd.DataFrame) -> pd.Series:
        self._initialize(df)
        self.__algorithm__()
        return self._positions.copy()


SimpleAlgorithm = AlphaStrategy  # Alias for backward compatibility
```

### Step 5: Define `AlphaEngine` Facade Class
```python
class AlphaEngine:
    """
    Core backtesting engine facade for Alpha Farm.
    Integrates XNOBacktestEngine for realistic VN30F futures simulation.
    """
    def __init__(
        self,
        initial_capital: float = 1_000_000_000.0,
        margin_rate: float = 0.285,
        maintenance_margin_rate: float = 0.185,
        fee_per_contract: float = 6000.0,
        multiplier: float = 100.0,
        rollover_penalty_points: float = 1.5,
    ):
        self.backtest_engine = XNOBacktestEngine(
            initial_capital=initial_capital,
            margin_rate=margin_rate,
            maintenance_margin_rate=maintenance_margin_rate,
            fee_per_contract=fee_per_contract,
            multiplier=multiplier,
            rollover_penalty_points=rollover_penalty_points,
        )

    def run(self, strategy: AlphaStrategy, df: pd.DataFrame) -> BacktestResult:
        """
        Executes backtest for the given strategy and historical data.
        """
        return self.backtest_engine.run(strategy, df)

    def evaluate(self, strategy: AlphaStrategy, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Executes backtest and calculates strategy risk/return metrics.
        """
        result = self.run(strategy, df)
        metrics = compute_metrics(result.equity_curve)
        metrics['total_fees'] = result.total_fees
        metrics['total_trades'] = result.total_trades
        metrics['final_equity'] = result.final_equity
        return metrics
```

---

## 6. Verification and Validation Checklist

1. **Clean Code & No Legacy Traces**:
   - `grep_search` for `import talib` returns 0 in `AlphaEngine.py`.
   - `grep_search` for `FeatureEngine` returns 0 in `AlphaEngine.py`.
   - `grep_search` for `OperatorEngine` returns 0 in `AlphaEngine.py`.
   - `grep_search` for `_validate_sandbox_constraints` returns 0 in `AlphaEngine.py`.

2. **Interface Integrity**:
   - `AlphaEngine.run(strategy, df)` returns valid `BacktestResult`.
   - `AlphaEngine.evaluate(strategy, df)` returns dict containing `sharpe`, `max_drawdown`, `annualized_return`, `total_fees`, `total_trades`, `final_equity`.
   - Backward compatibility aliases `DataProxy` and `SimpleAlgorithm` ensure seamless execution for existing strategy definitions.

3. **Futures Market Simulation Fidelity**:
   - VN30F futures initial margin (28.5%), maintenance margin (18.5%), contract fee (6,000 VND), multiplier (100 VND/pt), intra-bar margin call liquidations, and 3rd Thursday rollover penalties are fully preserved via `XNOBacktestEngine`.
