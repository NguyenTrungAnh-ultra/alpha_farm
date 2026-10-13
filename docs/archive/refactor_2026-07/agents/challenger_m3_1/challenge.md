# Challenge Report — Milestone 3: Refactor Engine to AlphaEngine

**Agent**: Challenger M3.1 (critic, specialist)  
**Target Component**: `core_engine/AlphaEngine.py`, `AlphaStrategy`, `AlphaDataProxy`  
**Date**: 2026-07-21  

---

## Challenge Summary

**Overall risk assessment**: **LOW**

The refactored `AlphaEngine` facade and `AlphaStrategy` base class demonstrate robust API design, correct position shifting (preventing lookahead bias), proper data proxy encapsulation, and graceful fallback handling for missing volume columns.

All 8 empirical stress scenarios pass. One minor edge-case observation was identified in `CalculateMetrics.py` when evaluating empty DataFrames (where `max_drawdown_pct` returns `NaN` instead of `0.0`).

---

## Challenges

### [Low] Challenge 1: Empty DataFrame metrics evaluation yields NaN for `max_drawdown_pct`

- **Assumption challenged**: `CalculateMetrics.compute_metrics()` assumes `daily_equity` contains at least 1 bar when calculating maximum drawdown.
- **Attack scenario**: Passing an empty DataFrame (`len(df) == 0`) to `AlphaEngine.evaluate()`.
- **Blast radius**: `result.equity_curve` is empty. Line 140 of `CalculateMetrics.py` evaluates `drawdown.min() * 100`. Calling `.min()` on an empty Series returns `np.nan`, setting `metrics['max_drawdown_pct'] = np.nan`.
- **Mitigation**: Update line 140 in `CalculateMetrics.py` to check `if len(daily_equity) > 0 else 0.0` (or `fillna(0.0)`).

---

## Stress Test Results

| # | Scenario / Test Case | Expected Behavior | Actual Behavior | Result |
|---|----------------------|-------------------|-----------------|--------|
| 1 | `AlphaStrategy` Subclassing & Position Generation | `run_algorithm()` generates aligned `pd.Series` position targets using boolean masks | Targets generated with matching index and correct position values (`0.4`, `-0.4`, `0.0`) | **PASS** |
| 2 | Keyword Arguments & Parameters | `params` dict populated and attributes assigned dynamically (`self.vol_threshold`) | Attributes assigned correctly and accessible within `__algorithm__()` | **PASS** |
| 3 | `AlphaEngine.run()` on Synthetic Data | Returns `BacktestResult` with mark-to-market equity curve, trade list, and fee calculation | Equity curve generated for 300/500 bars, fees and trades calculated accurately | **PASS** |
| 4 | `AlphaEngine.evaluate()` on Synthetic Data | Returns dictionary of transaction, performance, and risk metrics | Dictionary returned with all expected metrics (CAGR, Sharpe, MDD, VaR, Sortino, etc.) | **PASS** |
| 5 | Flat Strategy (Zero Trades) | 0 trades recorded, equity remains constant at `initial_capital`, fees = 0.0 | Equity curve is constant, 0 trades, 0 fees, `net_equity = initial_capital` | **PASS** |
| 6 | Empty DataFrame (0 rows) | `run()` returns empty equity curve without crashing; `evaluate()` completes | `run()` returns 0-length result cleanly; `evaluate()` completes (`max_drawdown_pct` is `NaN`) | **PASS (with note)** |
| 7 | Single-Row DataFrame (1 row) | Signal shifted out by `shift(1)`, 0 trades entered, equity = `initial_capital` | Signal shifted to `0.0`, 0 trades executed, equity curve has 1 bar | **PASS** |
| 8 | Missing 'Volume' Column | `AlphaDataProxy` defaults `volume` to all-zero `pd.Series`; backtest executes | `proxy.volume` is `0.0` Series; strategy & backtest complete without error | **PASS** |
| 9 | Missing Core Price Columns ('Open', 'High', 'Low', 'Close') | Raises `KeyError` when strategy or engine accesses missing column | Raises expected `KeyError` | **PASS** |
| 10| Zero Volume Data | Data proxy sets `volume` to `0.0`; price strategy unaffected; volume strategy yields 0 positions | Price strategy trades normally; volume strategy yields 0 positions | **PASS** |

---

## Unchallenged Areas

- **C-extension TA-Lib interactions**: Out of scope for Milestone 3 (TA-Lib dependencies were removed in Milestone 1).
- **MCTS Search Space Integration**: MCTSDimensions primitive search space modification is scheduled for Milestone 4.
