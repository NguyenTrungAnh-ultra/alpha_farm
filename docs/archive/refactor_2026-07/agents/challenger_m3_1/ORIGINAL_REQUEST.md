## 2026-07-21T08:09:34Z
<USER_REQUEST>
You are Challenger M3.1 for Milestone 3 (Refactor Engine to AlphaEngine).
Your working directory is f:\Projects\alpha_farm\.agents\challenger_m3_1. Create this directory if it doesn't exist.
Read:
- f:\Projects\alpha_farm\PROJECT.md
- f:\Projects\alpha_farm\.agents\worker_m3\handoff.md

Tasks:
1. Write and run an empirical stress test for `AlphaEngine`:
   - Test `AlphaStrategy` subclassing and custom strategy position generation.
   - Test `AlphaEngine.run()` and `AlphaEngine.evaluate()` on synthetic price data (DataFrame with OHLCV columns).
   - Test edge cases: empty DataFrame, single-row DataFrame, missing columns, zero volume.
2. Run `pytest tests/`.
3. Document empirical test results in f:\Projects\alpha_farm\.agents\challenger_m3_1\challenge.md and handoff.md.
4. Send report back to parent using send_message.
</USER_REQUEST>
