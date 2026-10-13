## 2026-07-21T15:07:13Z
You are Worker M3 for Milestone 3: Refactor Engine to AlphaEngine.
Your working directory is f:\Projects\alpha_farm\.agents\worker_m3. Create this directory if it doesn't exist.
Read:
- f:\Projects\alpha_farm\PROJECT.md
- f:\Projects\alpha_farm\.agents\orchestrator\plan.md
- f:\Projects\alpha_farm\.agents\explorer_m3_1\handoff.md
- f:\Projects\alpha_farm\.agents\explorer_m3_2\handoff.md
- f:\Projects\alpha_farm\.agents\explorer_m3_3\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Tasks to implement:
1. Create `core_engine/AlphaEngine.py`:
   - Stripped of `talib`, `FeatureEngine`, `OperatorEngine`, `TALIB_NAME_MAPPING`, `_load_feature_whitelist()`, `_validate_sandbox_constraints()`.
   - Class `AlphaDataProxy` (with top-level alias `DataProxy = AlphaDataProxy`).
   - Class `AlphaStrategy` (with top-level alias `SimpleAlgorithm = AlphaStrategy`), without `self.feat` or `self.op`.
   - Class `AlphaEngine`: Facade wrapping `XNOBacktestEngine` (from `core_engine.BacktestEngine`) and `compute_metrics` (from `core_engine.CalculateMetrics`).
2. Delete `core_engine/XnoEngine.py`.
3. Update imports across the codebase:
   - `strategy_workflows/MCTSEngine.py`: change `from core_engine.XnoEngine import SimpleAlgorithm` to `from core_engine.AlphaEngine import SimpleAlgorithm, AlphaStrategy`.
   - `strategy_workflows/RunMCTS.py`: update lines 67, 98, 129, 176 from `XnoEngine` to `AlphaEngine`.
   - `refactor_imports.py`: update import regex rules from `XnoEngine` to `AlphaEngine`.
   - `docs/ARCH.md`: update references from `XnoEngine` to `AlphaEngine`.
   - `core_engine/BacktestEngine.py`: update docstring reference.
4. Run verification commands:
   - `python -c "from core_engine.AlphaEngine import AlphaEngine, AlphaStrategy, AlphaDataProxy, SimpleAlgorithm, DataProxy; print('IMPORT_SUCCESS')"`
   - `pytest tests/`
5. Record changes, build/test results, and verification output in f:\Projects\alpha_farm\.agents\worker_m3\changes.md and handoff.md.
6. Send completion message back to parent using send_message.
