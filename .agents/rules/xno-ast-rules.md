---
trigger: always_on
---

# XNOQuant AST Rules

Follow strict AST rules for XNOQuant strategy. Sandbox reject bad code.

## 1. No Helper Function
- **FORBIDDEN** define any extra `def` (like `def abs`, `def sign`, `def rank`) inside `CustomStrategy`.
- Only allowed function inside class: `def __algorithm__(self):`.
- All math, logic, formulas (e.g. rank, z-score, decay_linear) must inline directly inside `__algorithm__`.

## 2. No Init Function
- **FORBIDDEN** use `def __init__(self):`.
- Define params or constants as `self.param_name = value` at top of `__algorithm__`.

## 3. No External Import
- **FORBIDDEN** use `import` or `from` (e.g. `import numpy as np`, `import pandas as pd`).
- Sandbox block external lib. Use provided method via `self` attribute (`self.feat`, `self.op`, `self.data`) or allowed native pandas Series method (`.where()`, `.fillna()`, `.ffill()`).

## Correct Structure Example
```python
class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # Define params at top
        self.window = 20
        self.stop_loss = 15.0
        
        close = self.data.pv_close
        vwap = self.feat.rolling_mean(close, self.window)
        
        # Inline all helper logic here
        diff = close - vwap
        abs_diff = self.op.where(diff > 0, diff, -diff)
        
        # Set positions
        raw_pos = self.op.where(abs_diff > 10, 1.0, 0.0)
        self.set_positions(raw_pos == 0.0, position=0.0)
        self.set_positions(raw_pos == 1.0, position=1.0)
```

## 4. Anti-Singularity Rule
- VN derivative market has many candles with `Volume = 0` or `High - Low = 0`.
- **FORBIDDEN** direct divide by Volume or price range (like `close / volume` or `close / (high - low)`). Cause `NaN` or `Inf` error (divide by 0). Crash Sandbox.
- Must use safe system function: `self.op.isfinite()` and `self.op.zero_ifna()` to protect. OR add tiny constant `1e-8` to denominator.
- **Correct example:** `safe_signal = self.op.where(self.op.isfinite(close / volume), close / volume, 0.0)`
