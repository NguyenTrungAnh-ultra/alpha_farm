## 2026-07-21T06:09:39Z
You are worker_m1 for Milestone 1 (Erase Sandbox & Legacy Traces) in alpha_farm refactoring.
Working directory: f:\Projects\alpha_farm\.agents\teamwork_preview_worker_m1
Project file: f:\Projects\alpha_farm\PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Task:
1. Delete the following 4 legacy files:
   - f:\Projects\alpha_farm\core_engine\PlatformEmulator.py
   - f:\Projects\alpha_farm\strategy_workflows\SubmitStrategies.py
   - f:\Projects\alpha_farm\utilities\SandboxPrefixer.py
   - f:\Projects\alpha_farm\core_engine\RestrictedSeries.py
2. Modify dependent files to remove all imports and references to these 4 files:
   - f:\Projects\alpha_farm\strategy_workflows\HMMValidation.py: Replace XNOPlatformEmulator with XNOBacktestEngine from core_engine.BacktestEngine.
   - f:\Projects\alpha_farm\main.py: Remove cmd_submit, SubmitStrategies import, and all CLI/interactive submit options.
   - f:\Projects\alpha_farm\core_engine\BacktestEngine.py: Remove RestrictedSeries unwrapping check on lines 195-197.
   - f:\Projects\alpha_farm\strategy_workflows\RunMCTS.py: Remove RestrictedSeries logger configuration on line 177.
   - f:\Projects\alpha_farm\core_engine\XnoEngine.py: Remove import of RestrictedSeries, replace RestrictedSeries(df['Open']) wrappers with df['Open'] in DataProxy and SimpleAlgorithm.
   - f:\Projects\alpha_farm\refactor_imports.py: Remove mappings/rules for PlatformEmulator, RestrictedSeries, SubmitStrategies, SandboxPrefixer.
3. Run `pytest tests/` to confirm all current tests pass.
4. Write changes report and handoff report in f:\Projects\alpha_farm\.agents\teamwork_preview_worker_m1\handoff.md with full command outputs and build/test verification. Send completion message back to parent.
