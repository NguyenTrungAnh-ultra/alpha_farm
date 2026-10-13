# Handoff Report — Explorer M4.3: MCTS Strategy Tree Sampling & Evaluation Pipeline Audit

## 1. Observation
1. **`strategy_workflows/MCTSEngine.py` (lines 75–117)**: `ast_to_code()` renders function calls using prefixes `self.op` and `self.feat`:
   - Line 76: `prefix = "self.op" if group in [OperatorGroup.LOGIC, OperatorGroup.TIME_SERIES] else "self.feat"`
   - Lines 80, 84, 86, 88, 90, 92, 94, 98, 100, 102, 104: Render `self.feat.macd`, `self.feat.bbands`, `self.feat.vwap`, `self.feat.adx`, `self.feat.stoch`, `self.feat.doji`, etc.
   - Line 117: `return f"{prefix}.{node.name}({', '.join(args)})"`
2. **`strategy_workflows/MCTSEngine.py` (lines 286, 329, 367–368, 373, 575–576, 580, 583–584, 586–587, 590–591)**: Strategy subclasses (`BooleanMCTSStrategy`, `RatioMCTSStrategy`, `NormalizedMCTSStrategy`) and `evaluate_expression()` call `self.op.where(...)`, `self.feat.rolling_mean(...)`, and `self.feat.rolling_std(...)`.
3. **`core_engine/AlphaEngine.py` (lines 97–159)**: `AlphaStrategy` (and alias `SimpleAlgorithm`) was stripped of `self.feat` and `self.op` in Milestones 1 and 3. Running `self.feat` or `self.op` on any `AlphaStrategy` instance raises `AttributeError: 'NormalizedMCTSStrategy' object has no attribute 'feat'`.
4. **`strategy_workflows/MCTSEngine.py` (lines 554–565)**: `globals_dict` passed to `eval(expr_str, {}, globals_dict)` contains only `{'self', 'close', 'high', 'low', 'open_', 'volume'}` and lacks top-level functions from `core_engine/AlphaPrimitives.py` (`ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, `ts_argmin`).
5. **`strategy_workflows/RunMCTS.py` (lines 80–86, 117, 142)**: `generate_strategy_code()` emits Python source code referencing `self.feat.rolling_mean(...)`, `self.feat.rolling_std(...)`, and `self.op.where(...)` without importing `AlphaPrimitives.py` routines.
6. **`core_engine/AlphaPrimitives.py` (lines 1–181)**: Implements 9 pure NumPy vectorized functions (`ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_rank`, `ts_corr`, `ts_zscore`, `ts_argmax`, `ts_argmin`) wrapped by `@ts_primitive`.

---

## 2. Logic Chain
1. **Observation 1 & 3**: In Milestones 1 and 3, legacy `FeatureEngine` (`self.feat`) and `OperatorEngine` (`self.op`) were removed from `AlphaEngine.py`. `ast_to_code()` in `MCTSEngine.py` continues to produce code string expressions referencing `self.feat` and `self.op`.
2. **Observation 2 & 3**: When `evaluate_expression()` executes `eval(expr_str, ..., globals_dict)`, any generated expression referencing `self.feat` or `self.op` immediately throws an `AttributeError`.
3. **Observation 2 & 4**: Even if expressions did not reference `self.feat`/`self.op`, evaluating primitive calls like `ts_mean(close, 20)` would fail with `NameError: name 'ts_mean' is not defined` because `globals_dict` lacks imports from `AlphaPrimitives.py`.
4. **Observation 2 & 3**: Position masking inside `evaluate_expression()` relies on `self.temp_strat.op.where(...)`. Raising an `AttributeError` triggers the `except Exception:` handler, causing 100% of candidate evaluations to return `best_reward = -10.0`.
5. **Observation 5 & 6**: Strategy files emitted by `RunMCTS.py` contain `self.feat` and `self.op` calls and lack `AlphaPrimitives` imports, creating broken strategy files upon output.
6. **Conclusion**: To restore full MCTS strategy discovery functionality, `MCTSEngine.py` and `RunMCTS.py` must be updated to remove all `self.feat`/`self.op` references, import `AlphaPrimitives.py` routines into `globals_dict`, update `ast_to_code()` for primitive rendering, and use `np.where` for position masking.

---

## 3. Caveats
- This investigation is strictly read-only and did not alter source code files outside the `.agents/` directory.
- `MCTSDimensions.py` operator registry updates (removing legacy TA-Lib indicators and registering new `AlphaPrimitives`) are covered by sister tasks Explorer M4.1 and M4.2.
- Backtest speed and multi-core parallelism in `RunMCTS.py` rely on `ProcessPoolExecutor`; no changes to process pooling logic are required.

---

## 4. Conclusion
The MCTS discovery pipeline (`MCTSEngine.py` and `RunMCTS.py`) currently fails 100% of strategy tree evaluations due to legacy `self.feat` and `self.op` references. To achieve full integration with `AlphaPrimitives.py` and `AlphaEngine.py`:
1. `ast_to_code()` in `MCTSEngine.py` must be updated to output top-level primitive expressions (`ts_mean`, `ts_sum`, `ts_corr`, etc.) and standard arithmetic/logical operators without `self.feat` or `self.op` prefixes.
2. `globals_dict` in `evaluate_expression` must expose all 9 `AlphaPrimitives` functions and `np`.
3. `evaluate_expression()` and strategy templates must replace `self.feat.rolling_mean/std` and `self.op.where` with `ts_zscore` / `ts_mean` and `np.where`.
4. `generate_strategy_code()` in `RunMCTS.py` must emit valid Python files importing `AlphaPrimitives` and `np`.

---

## 5. Verification Method
1. **File Inspection**:
   - Inspect `strategy_workflows/MCTSEngine.py` lines 75–117, 286, 329, 367–373, 554–591 to verify occurrences of `self.feat`, `self.op`, and `globals_dict`.
   - Inspect `strategy_workflows/RunMCTS.py` lines 80–86, 117, 142 for generated code templates.
2. **Execution Test**:
   - Run Python code snippet evaluating a candidate expression via `evaluate_expression()` after applying primitive updates:
     ```python
     from strategy_workflows.MCTSEngine import MCTSEngine
     from strategy_workflows.SemanticCompiler import ASTNode
     mcts = MCTSEngine('10m')
     # AST: ts_mean(pv_close, 20)
     node = ASTNode("ts_mean", [ASTNode("pv_close"), ASTNode("Constant", value=20)])
     reward, direction, metrics = mcts.evaluate_expression(node)
     ```
   - Invalidation Condition: Evaluation raises `AttributeError`, `NameError`, or returns default `-10.0` reward for valid mathematical expressions.
