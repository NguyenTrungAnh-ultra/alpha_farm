from agent.prompts import TALIB_INDICATORS, TIMEFRAME_HINTS, STRATEGY_FAMILIES

def build_deepseek_system_prompt(experience: str = "") -> str:
    """
    Build the STATIC system prompt for DeepSeek.
    This must NOT contain any variables that change per iteration.
    This ensures DeepSeek can cache this heavy prompt.
    """
    exp_section = f"\n## COMBAT EXPERIENCE (MANDATORY READING)\n{experience}\n" if experience else ""

    return f"""You are an expert **Quant Researcher** designing trading strategies for the **VN30F1M futures contract** (VN30 index derivatives on the Vietnamese market).

{exp_section}
## Quality Requirements
- The strategy must have **CLEAR entry/exit logic**, not vague, expressed using mathematical formulas.
- Must use **at least 2 indicators** (1 primary + 1 filter/confirmation).
- Must have its **own exit logic** (do not just reverse signals).
- Parameters must have **reasonable search spaces** for optimization.
- Must be **COMPLETELY DIFFERENT** from any strategy mentioned by the user.

{TALIB_INDICATORS}

## Timeframe Guidance
{chr(10).join(f"- {k}: {v.strip()}" for k, v in TIMEFRAME_HINTS.items())}

## Output Format — MUST return EXACT JSON structure below:

```json
{{
    "name": "StrategyName",
    "timeframe": "1m|3m|5m|10m|15m|30m|1H",
    "family": "trend-following|momentum|mean-reversion|breakout|volatility|multi-indicator|pattern-based|channel|oscillator-divergence|session-based",
    "description": "Brief description of the strategy logic",
    "formula": {{
        "inputs": ["close", "high", "low", "volume"],
        "indicators": [
            {{"name": "EMA_fast", "definition": "EMA(close, timeperiod=10)"}},
            {{"name": "ATR", "definition": "ATR(high, low, close, timeperiod=14)"}}
        ],
        "entry_long": "Specific mathematical formula to enter LONG (e.g.: close > EMA_fast + 0.5 * ATR)",
        "entry_short": "Specific mathematical formula to enter SHORT",
        "exit_logic": "Exit conditions (applied commonly or separately)"
    }},
    "param_space": {{
        "param_name": {{"type": "int|float", "low": 5, "high": 30, "step": 1}},
        "another_param": {{"type": "float", "low": 0.5, "high": 3.0, "step": 0.1}}
    }}
}}
```

IMPORTANT: Return ONLY valid JSON. Do not add any text outside the JSON block.
"""

def build_deepseek_user_prompt(
    timeframe: str,
    existing_strategies: list[dict],
    round_num: int,
    total_rounds: int,
    tried_names: list[str] = None,
) -> str:
    """
    Build the DYNAMIC user prompt for DeepSeek.
    This contains information that changes per iteration.
    """
    
    # Format existing strategies list
    if existing_strategies:
        existing_list = "\n".join([
            f"  - [{s['timeframe']}] {s['name']} ({s['family']}): {s.get('description', '')[:80]}"
            for s in existing_strategies
        ])
        existing_section = f"""
## THERE ARE ALREADY {len(existing_strategies)} ACCEPTED STRATEGIES — DO NOT DUPLICATE:
{existing_list}

→ You must create a COMPLETELY DIFFERENT strategy: use different indicators, different logic, or a different family.
"""
    else:
        existing_section = "\n## This is the FIRST strategy — choose a strong and diverse approach.\n"
    
    # Add ALL tried strategy names
    if tried_names:
        tried_list = ", ".join(sorted(tried_names))
        tried_section = f"""
## PREVIOUSLY TRIED STRATEGY NAMES (DO NOT REUSE):
{tried_list}

→ ABSOLUTELY DO NOT reuse any names listed above. You must use a COMPLETELY NEW name and DIFFERENT indicators/logic.
"""
    else:
        tried_section = ""

    # Pick suggested family
    used_families = [s.get('family', '') for s in existing_strategies]
    unused_families = [f for f in STRATEGY_FAMILIES if f not in used_families]
    if unused_families:
        suggested = f"Suggested unused families: **{', '.join(unused_families[:3])}**"
    else:
        suggested = "All families have been used. Please create a highly creative and distinctive VARIATION."

    return f"""## Task
Design 1 intraday trading strategy for the **{timeframe}** timeframe.
This is round {round_num}/{total_rounds}.

{existing_section}

{tried_section}

{suggested}
"""
