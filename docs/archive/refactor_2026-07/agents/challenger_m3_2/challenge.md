# Challenge Report: Milestone 3 Engine Refactoring to AlphaEngine

**Agent**: Challenger M3.2 (Empirical Challenger)  
**Milestone**: Milestone 3 - Refactor Engine to AlphaEngine  
**Target Path**: `f:\Projects\alpha_farm\.agents\challenger_m3_2\challenge.md`  
**Date**: 2026-07-21  

---

## Challenge Summary

**Overall risk assessment**: LOW

Empirical testing and codebase-wide static audit confirm that the core engine refactoring from `XnoEngine.py` to `AlphaEngine.py` is complete, functional, and clean. All unit tests pass with zero failures. Two minor lingering reference observations (1 in migration utility script regex, 1 in prompt docstring comment) were surfaced.

---

## Challenges & Observations

### 1. [Low Risk] Lingering `XnoEngine` references in migration utility `refactor_imports.py`

- **Assumption challenged**: Claim that `git grep "XnoEngine" -- '*.py'` returns 0 active matches across all `.py` files in `f:\Projects\alpha_farm`.
- **Observation / Empirical Evidence**:
  Grep search across `*.py` files in `f:\Projects\alpha_farm` returned 3 matches in `refactor_imports.py`:
  - `refactor_imports.py` line 40: `(r'from core_engine\.XnoEngine import', r'from core_engine.AlphaEngine import'),`
  - `refactor_imports.py` line 41: `(r'import core_engine\.XnoEngine', r'import core_engine.AlphaEngine'),`
  - `refactor_imports.py` line 42: `(r'core_engine\.XnoEngine', r'core_engine.AlphaEngine'),`
- **Blast radius**: Minimal. `refactor_imports.py` is a migration helper script for updating import statements. It is not part of the active strategy discovery or execution runtime. Zero production runtime files (`core_engine/`, `strategy_workflows/`, `llm_clients/`, `utilities/`, `tests/`) reference `XnoEngine`.
- **Mitigation**: Retaining the regex pattern in `refactor_imports.py` ensures legacy code imported in the future can be refactored automatically. However, if strict 0-match compliance across all `.py` files is enforced, this script could be moved or excluded.

### 2. [Low Risk] Lingering `talib` reference in prompt comment `utilities/Prompts.py`

- **Assumption challenged**: Complete elimination of `talib` string references across utility modules.
- **Observation / Empirical Evidence**:
  Grep search for `talib` across `*.py` files returned 1 match:
  - `utilities/Prompts.py` line 11: `# ─── Available talib & SDK indicators (curated for futures) ────────────────`
- **Blast radius**: Zero runtime impact. There are **0 active imports** (`import talib`) or C-extension calls in any Python source file.
- **Mitigation**: Update `utilities/Prompts.py` comment during Milestone 4 ("Update MCTSDimensions Search Space") when LLM prompts are updated for `AlphaPrimitives`.

### 3. [Pass] `FeatureEngine` & `OperatorEngine` Deprecation Audit

- **Assumption challenged**: Verification of total removal of `FeatureEngine` and `OperatorEngine`.
- **Observation / Empirical Evidence**:
  - `grep_search` query `FeatureEngine` on `*.py` files: **0 matches**.
  - `grep_search` query `OperatorEngine` on `*.py` files: **0 matches**.
- **Blast radius**: N/A (Fully verified).

---

## Stress & Test Suite Verification Results

| Test Module / Scenario | Commands Executed | Expected | Actual | Pass / Fail |
|------------------------|-------------------|----------|--------|-------------|
| Pytest Test Suite | `python -m pytest tests/` | 100% pass across core modules | 25 passed, 1 skipped (`test_hmm_validation.py` skipped due to missing `hmmlearn`) | PASS |
| Primitive Operations | `tests/test_alpha_primitives.py` | 9 tests pass | 9 passed | PASS |
| Core Engine Facade | `tests/test_core_engine.py` | 5 tests pass | 5 passed | PASS |
| Hardware Concurrency | `tests/test_hardware_concurrency.py` | 1 test passes | 1 passed | PASS |
| MCTS Strategy Engine | `tests/test_mcts_engine.py` | 2 tests pass | 2 passed | PASS |
| Semantic AST Compiler | `tests/test_semantic_compiler.py` | 8 tests pass | 8 passed | PASS |

---

## Unchallenged Areas

- **`docs/ARCH.md` legacy documentation references**: Contains historical references explaining why sandbox AST imports were banned. These remain in architecture documentation for contextual history and are scheduled for doc cleanup in Milestone 5.
