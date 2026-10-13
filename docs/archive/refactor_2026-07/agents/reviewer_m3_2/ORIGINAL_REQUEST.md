## 2026-07-21T08:09:34Z
You are Reviewer M3.2 for Milestone 3 (Refactor Engine to AlphaEngine).
Your working directory is f:\Projects\alpha_farm\.agents\reviewer_m3_2. Create this directory if it doesn't exist.
Read:
- f:\Projects\alpha_farm\PROJECT.md
- f:\Projects\alpha_farm\.agents\worker_m3\handoff.md

Tasks:
1. Review interface contracts between `AlphaEngine`, `BacktestEngine`, and downstream execution scripts (`MCTSEngine.py`, `RunMCTS.py`).
2. Verify backward-compatibility aliases `SimpleAlgorithm = AlphaStrategy` and `DataProxy = AlphaDataProxy`.
3. Run `pytest tests/` and verify 0 failures.
4. Document findings in f:\Projects\alpha_farm\.agents\reviewer_m3_2\review.md and handoff.md.
5. Send review verdict (PASS/VETO) back to parent using send_message.
