## 2026-07-21T08:04:04Z

<USER_REQUEST>
You are Explorer M3.3 for Milestone 3: Refactor Engine to AlphaEngine.
Your working directory is f:\Projects\alpha_farm\.agents\explorer_m3_3. Create this directory if it doesn't exist.
Read f:\Projects\alpha_farm\PROJECT.md and f:\Projects\alpha_farm\.agents\orchestrator\plan.md.

Task:
1. Examine interface contracts between `AlphaEngine` / `BacktestEngine` and downstream strategy execution workflows (`strategy_workflows/MCTSEngine.py`, `strategy_workflows/SemanticCompiler.py`, `strategy_workflows/GenerateStrategies.py`, `main.py`).
2. Verify how input data (DataFrame / Numpy ndarray) is passed into the backtest engine and how metrics/returns are calculated.
3. Confirm that no `RestrictedSeries` objects or TA-Lib features remain in the pipeline data flow.
4. Ensure `BacktestEngine` interface is intact and clean for VN30F backtesting.
5. Write your detailed analysis to f:\Projects\alpha_farm\.agents\explorer_m3_3\analysis.md and handoff.md.
6. Send your report path and summary back to parent using send_message.
Remember: Do NOT edit source code files outside your .agents folder.
MANDATORY INTEGRITY WARNING: Do NOT cheat, fake, or compromise verification. All findings must be based on actual file analysis.
</USER_REQUEST>
