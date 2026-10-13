# Detailed Audit & Import Replacement Analysis: Refactoring XnoEngine to AlphaEngine

## 1. Executive Summary & Audit Scope

This report delivers a complete, codebase-wide audit across `f:\Projects\alpha_farm` for all occurrences of and references to:
1. `XnoEngine` (and `core_engine.XnoEngine`)
2. `FeatureEngine`
3. `OperatorEngine`
4. `from core_engine.XnoEngine import ...` or `import core_engine.XnoEngine`

The objective is to enable seamless refactoring from legacy engine modules (`XnoEngine.py`, `FeatureEngine`, `OperatorEngine`) to the clean, decoupled `AlphaEngine.py` and `BacktestEngine.py`.

---

## 2. Complete Search Findings by File and Line Number

A comprehensive search across the entire project structure (`core_engine/`, `strategy_workflows/`, `tests/`, `docs/`, root scripts) identified 7 primary files containing occurrences or legacy references.

### 2.1 File: `core_engine/XnoEngine.py` (Target of File Rename -> `core_engine/AlphaEngine.py`)
This file is the legacy module scheduled for replacement by `core_engine/AlphaEngine.py`.

| Line Number | Category | Content / Context |
|-------------|----------|-------------------|
| Line 2 | `XnoEngine` | Docstring header `# XnoEngine` |
| Line 7 | `FeatureEngine` | Docstring: `1. FeatureEngine: Mocks self.feat.*, providing standard technical indicators` |
| Line 10 | `OperatorEngine` | Docstring: `2. OperatorEngine: Mocks self.op.*, implementing 30 custom logical and causal operators` |
| Line 13 | `SimpleAlgorithm` | Docstring: `4. SimpleAlgorithm: The base class for user-defined strategies` |
| Line 24 | `XnoEngine` | `logger = logging.getLogger("core_engine.XnoEngine")` |
| Line 28 | `FeatureEngine` | Docstring: `Load the whitelist of allowed feature methods for the FeatureEngine.` |
| Line 37 | `FeatureEngine` | Docstring: `A set of lowercase function names permitted under FeatureEngine.` |
| Line 107 | `FeatureEngine` | `class FeatureEngine:` (Class definition spanning lines 107–490) |
| Lines 184–359 | `FeatureEngine` | 28 `logger.debug` statements (e.g. `logger.debug("FeatureEngine.rolling_mean called...")`) |
| Line 403 | `FeatureEngine` | `raise AttributeError(f"'FeatureEngine' object has no attribute '{name}'")` |
| Line 425 | `FeatureEngine` | `logger.debug(f"FeatureEngine.{name} called")` |
| Line 491 | `OperatorEngine` | `class OperatorEngine:` (Class definition spanning lines 491–760) |
| Lines 523–757 | `OperatorEngine` | 30 `logger.debug` statements (e.g. `logger.debug("OperatorEngine.crossed called")`) |
| Line 782 | `SimpleAlgorithm` | `class SimpleAlgorithm:` (Base strategy class definition) |
| Line 791 | `SimpleAlgorithm` | `logger.debug(f"Initializing SimpleAlgorithm with params: {kwargs}")` |
| Line 793 | `FeatureEngine` | `self.feat: FeatureEngine = None` |
| Line 794 | `OperatorEngine` | `self.op: OperatorEngine = None` |
| Line 804 | Both | `logger.debug("Setting up strategy environment (DataProxy, FeatureEngine, OperatorEngine)")` |
| Line 806 | `FeatureEngine` | `self.feat = FeatureEngine()` |
| Line 807 | `OperatorEngine` | `self.op = OperatorEngine()` |

### 2.2 File: `strategy_workflows/MCTSEngine.py`
| Line Number | Category | Content / Context |
|-------------|----------|-------------------|
| Line 20 | Import | `from core_engine.AlphaEngine import AlphaStrategy, SimpleAlgorithm` (Refactored from legacy `from core_engine.XnoEngine import SimpleAlgorithm`) |
| Line 75–76 | Comments | `# General function call: self.op or self.feat` |
| Line 263 | Class Def | `class BooleanMCTSStrategy(SimpleAlgorithm):` |
| Line 299 | Class Def | `class RatioMCTSStrategy(SimpleAlgorithm):` |
| Line 340 | Class Def | `class NormalizedMCTSStrategy(SimpleAlgorithm):` |

### 2.3 File: `strategy_workflows/RunMCTS.py`
| Line Number | Category | Content / Context |
|-------------|----------|-------------------|
| Line 67 | Generated Code String | `from core_engine.AlphaEngine import AlphaStrategy, SimpleAlgorithm` (In `NORMALIZED` strategy template) |
| Line 98 | Generated Code String | `from core_engine.AlphaEngine import AlphaStrategy, SimpleAlgorithm` (In `RATIO` strategy template) |
| Line 129 | Generated Code String | `from core_engine.AlphaEngine import AlphaStrategy, SimpleAlgorithm` (In `BOOLEAN` strategy template) |
| Line 176 | Logger | `logging.getLogger("core_engine.AlphaEngine").setLevel(logging.CRITICAL)` (Refactored from `logging.getLogger("core_engine.XnoEngine")`) |

### 2.4 File: `refactor_imports.py`
| Line Number | Category | Content / Context |
|-------------|----------|-------------------|
| Line 32 | Regex Replacement | `(r'from backtest\.strategy import', r'from core_engine.AlphaEngine import')` |
| Line 33 | Regex Replacement | `(r'import backtest\.strategy', r'import core_engine.AlphaEngine')` |
| Line 34 | Regex Replacement | `(r'backtest\.strategy', r'core_engine.AlphaEngine')` |
| Line 36 | Regex Replacement | `(r'from xno_sdk\.engine import', r'from core_engine.AlphaEngine import')` |
| Line 37 | Regex Replacement | `(r'import xno_sdk\.engine', r'import core_engine.AlphaEngine')` |
| Line 38 | Regex Replacement | `(r'xno_sdk\.engine', r'core_engine.AlphaEngine')` |
| Line 40 | Regex Replacement | `(r'from core_engine\.XnoEngine import', r'from core_engine.AlphaEngine import')` |
| Line 41 | Regex Replacement | `(r'import core_engine\.XnoEngine', r'import core_engine.AlphaEngine')` |
| Line 42 | Regex Replacement | `(r'core_engine\.XnoEngine', r'core_engine.AlphaEngine')` |

### 2.5 File: `tests/test_core_engine.py`
| Line Number | Category | Content / Context |
|-------------|----------|-------------------|
| Line 5–11 | Import | `from core_engine.AlphaEngine import (AlphaEngine, AlphaStrategy, AlphaDataProxy, SimpleAlgorithm, DataProxy)` |
| Line 64 | Alias Test | `assert SimpleAlgorithm is AlphaStrategy` |

### 2.6 File: `core_engine/BacktestEngine.py`
| Line Number | Category | Content / Context |
|-------------|----------|-------------------|
| Line 4 | Docstring | `Vectorized and bar-by-bar backtesting engine that simulates the exact behavior of XNOQuant.` |
| Line 114 | Docstring | `Engine backtest mô phỏng chính xác XNOQuant.` |
| Line 182 | Docstring Type Hint | `strategy : SimpleAlgorithm` |

### 2.7 File: `docs/ARCH.md`
| Line Number | Category | Content / Context |
|-------------|----------|-------------------|
| Line 54 | Documentation | `- XnoEngine.py: Lớp Wrapper cấp cao gom BacktestEngine và CalculateMetrics...` |

---

## 3. Formulated Exact Import Replacement Statements

To complete Milestone 3 engine refactoring, use the exact replacement statements formulated below for each affected file.

### 3.1 `strategy_workflows/MCTSEngine.py` (Line 20)
```python
# BEFORE (Legacy Import):
from core_engine.XnoEngine import SimpleAlgorithm

# AFTER (Refactored Import):
from core_engine.AlphaEngine import AlphaStrategy, SimpleAlgorithm
```

### 3.2 `strategy_workflows/RunMCTS.py` (Lines 67, 98, 129, 176)
```python
# BEFORE (Legacy Strategy Code Templates - Lines 67, 98, 129):
from core_engine.XnoEngine import SimpleAlgorithm

# AFTER (Refactored Strategy Code Templates - Lines 67, 98, 129):
from core_engine.AlphaEngine import AlphaStrategy, SimpleAlgorithm

# BEFORE (Legacy Logger Suppress - Line 176):
logging.getLogger("core_engine.XnoEngine").setLevel(logging.CRITICAL)

# AFTER (Refactored Logger Suppress - Line 176):
logging.getLogger("core_engine.AlphaEngine").setLevel(logging.CRITICAL)
```

### 3.3 `refactor_imports.py` (Lines 32–42)
```python
# BEFORE (Legacy Regex Replacements):
(r'from backtest\.strategy import', r'from core_engine.XnoEngine import'),
(r'import backtest\.strategy', r'import core_engine.XnoEngine'),
(r'backtest\.strategy', r'core_engine.XnoEngine'),
(r'from xno_sdk\.engine import', r'from core_engine.XnoEngine import'),
(r'import xno_sdk\.engine', r'import core_engine.XnoEngine'),
(r'xno_sdk\.engine', r'core_engine.XnoEngine'),

# AFTER (Refactored Regex Replacements):
(r'from backtest\.strategy import', r'from core_engine.AlphaEngine import'),
(r'import backtest\.strategy', r'import core_engine.AlphaEngine'),
(r'backtest\.strategy', r'core_engine.AlphaEngine'),
(r'from xno_sdk\.engine import', r'from core_engine.AlphaEngine import'),
(r'import xno_sdk\.engine', r'import core_engine.AlphaEngine'),
(r'xno_sdk\.engine', r'core_engine.AlphaEngine'),
```

### 3.4 `tests/test_core_engine.py` (Lines 4–11)
```python
# BEFORE (Legacy Imports):
from core_engine.XnoEngine import XnoEngine, SimpleAlgorithm, DataProxy

# AFTER (Refactored Imports):
from core_engine.BacktestEngine import XNOBacktestEngine, BacktestResult
from core_engine.AlphaEngine import (
    AlphaEngine,
    AlphaStrategy,
    AlphaDataProxy,
    SimpleAlgorithm,
    DataProxy,
)
```

### 3.5 `docs/ARCH.md` (Line 54)
```markdown
<!-- BEFORE -->
- `XnoEngine.py`: Lớp Wrapper cấp cao gom BacktestEngine và CalculateMetrics để thực thi và đánh giá chiến lược độc lập.

<!-- AFTER -->
- `AlphaEngine.py`: Lớp Wrapper cấp cao gom BacktestEngine và CalculateMetrics để thực thi và đánh giá chiến lược độc lập.
```

---

## 4. Architectural Summary & Recommendations

1. **`FeatureEngine` & `OperatorEngine` Removal**:
   - `FeatureEngine` (TALib wrapper) and `OperatorEngine` (30 sandbox operators) exist ONLY inside `core_engine/XnoEngine.py`.
   - Stripping them from `core_engine/AlphaEngine.py` eliminates all C-extension TA-Lib dependencies and sandbox overhead without breaking any external module, provided `AlphaStrategy` evaluates signals using NumPy or `AlphaPrimitives`.
2. **Backward Compatibility Aliases**:
   - In `core_engine/AlphaEngine.py`, maintain aliases:
     ```python
     SimpleAlgorithm = AlphaStrategy
     DataProxy = AlphaDataProxy
     ```
   - This ensures existing custom strategies and unit tests importing `SimpleAlgorithm` continue to execute without import failures.
