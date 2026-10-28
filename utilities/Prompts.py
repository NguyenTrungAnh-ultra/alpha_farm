"""
Prompts
=======
Prompt templates and builders for the Alpha Farm strategy generation pipeline.

Maintains dictionaries of timeframe hints, the library of available data fields/operators, 
and helper functions to construct structured LLM prompts for generating strategy 
blueprints and self-correction instructions.
"""

from strategy_workflows.MCTSDimensions import (
    OPERATOR_REGISTRY, OperatorGroup, UNIMPLEMENTED_OPERATORS, DATA_FIELD_DIMENSIONS,
)

# Data fields the OHLCV data provides (pv_vn30_close is declared but has no data behind it).
DATA_FIELDS = ["pv_open", "pv_high", "pv_low", "pv_close", "pv_volume"]
assert all(f in DATA_FIELD_DIMENSIONS for f in DATA_FIELDS)


def _operator_names(group: OperatorGroup) -> str:
    """Operators of a group that code generation supports, in registry order."""
    return ", ".join(
        op for op, meta in OPERATOR_REGISTRY.items()
        if meta["group"] == group and op not in UNIMPLEMENTED_OPERATORS
    )


# ─── Operator library, generated from the registry the compiler checks against ───
DIMENSIONAL_FUNCTIONS = f"""
## Available Data Fields
{', '.join(DATA_FIELDS)}  (or `?` to let the search choose the series)
"""

OPERATOR_FUNCTIONS = f"""
## Available Operator Functions

**Time-Series** (rolling window; the search picks the window length, never write it): {_operator_names(OperatorGroup.TIME_SERIES)}
  - Each takes ONE series argument, except `ts_corr` which takes two. Example: `ts_mean(?)`, `ts_corr(?, ?)`.
  - `ts_rank`, `ts_corr`, `ts_zscore` return a dimensionless RATIO. The others keep the dimension of their input.
**Math** (two series arguments): {_operator_names(OperatorGroup.STATISTICS)}
**[BOOLEAN_OUTPUT_FUNCTIONS]**: {_operator_names(OperatorGroup.LOGIC)}
  - `and_`, `or_`, `not_` take BOOLEAN arguments; `greater_than`, `less_than`, `equal` take two series and return BOOLEAN.
"""

# Every example must compile with SemanticCompiler (checked by tests).
FEW_SHOT_EXAMPLES = [
    ("statistical-mean-reversion", "sub(?, ts_mean(?))"),
    ("time-series-kinematics", "sub(ts_mean(?), ts_mean(?))"),
    ("volatility-regime", "sub(ts_max(?), ts_min(?))"),
    ("cross-dimensional-arbitrage", "mult(ts_zscore(?), ts_corr(?, ?))"),
    ("cross-dimensional-arbitrage, BOOLEAN root", "and_(greater_than(ts_mean(?), ts_mean(?)), less_than(ts_zscore(?), ts_corr(?, ?)))"),
]

# ─── Timeframe-specific guidance ────────────────────────────────────
TIMEFRAME_HINTS = {
    "1m": """
**1-Minute Timeframe** — Ultra Fast Scalping:
- Indicator periods: short-to-medium (5-20 bars)
- Trades: 10-30/day (high frequency)
- Suitable for: Fast momentum, micro-breakouts
- Stop loss: 1-3 points
- Extremely noisy. Needs very strong noise filters (e.g. a volume-based condition).
""",
    "3m": """
**3-Minute Timeframe** — Fast Scalping/Intraday:
- Indicator periods: short-to-medium (10-30 bars)
- Trades: 5-15/day
- Suitable for: Fast trend following, breakout confirmation
- Stop loss: 2-5 points
- Balanced noise and signal speed.
""",
    "5m": """
**5-Minute Timeframe** — Standard Intraday Scalping:
- Indicator periods: medium (12-30 bars)
- Trades: 4-10/day
- Suitable for: Trend pullback, breakout, volatility regimes
- Stop loss: 3-7 points
- Very popular timeframe with good liquidity and clean intraday swings.
""",
    "10m": """
**10-Minute Timeframe** — Balanced Intraday:
- Indicator periods: medium-to-long (10-40 bars)
- Trades: 2-5/day
- Suitable for: Trend confirmation, multi-indicator systems
- Stop loss: 5-10 points
""",
    "15m": """
**15-Minute Timeframe** — Swing Intraday:
- Indicator periods: longer (14-50 bars)
- Trades: 1-3/day
- Suitable for: High-quality trend-following, divergence, pattern recognition
- Stop loss: 8-15 points
- Fewer signals but much higher quality
""",
    "30m": """
**30-Minute Timeframe** — Position Intraday:
- Indicator periods: long (20-60 bars)
- Trades: 0-2/day (some days may have no trades)
- Suitable for: Major trends, range breakouts, session-based strategies
- Stop loss: 10-20 points
- Caution: Fewer bars per day, so indicators need sufficient lookback
""",
    "60m": """
**1-Hour Timeframe** — Position/Large Swing:
- Indicator periods: long (10-30 bars ≈ 2-6 days)
- Trades: 0-1/day (very rare, some weeks may have no trades)
- Suitable for: Major trend following, regime detection
- Stop loss: 15-30 points
- Requires appropriate indicator periods (only ~5 bars per day)
""",
}

# ─── Strategy families for diversity (Orthogonal & Quant-focused) ───
STRATEGY_FAMILIES = [
    "statistical-mean-reversion", # Z-score of price deviation from a rolling mean
    "time-series-kinematics",     # Differences of rolling means (momentum, acceleration)
    "volatility-regime",          # Rolling range and dispersion breakouts
    "cross-dimensional-arbitrage" # Combining price, volume and correlation series
]

# ═══════════════════════════════════════════════════════════════════════
# Prompt Builders
# ═══════════════════════════════════════════════════════════════════════

def build_idea_prompt(
    timeframe: str,
    existing_strategies: list[dict],
    round_num: int,
    total_rounds: int,
    market_regime: str = "High Volatility, Sideways",
    investment_thesis: str = "Exploit asymmetric skewness in order flow.",
    experience: str = "",
    tried_names: list[str] = None,
    fsa_forbidden_patterns: list[str] = None,
) -> str:
    """
    Build a structured prompt asking the LLM to generate a new trading strategy idea in JSON.
    
    Injects context libraries, timeframe specific indicators, diversity requirements (excluding
    already accepted strategies and previously failed names), and combat experience logs to 
    guide the LLM.
    
    Parameters
    ----------
    timeframe : str
        The target timeframe for the strategy (e.g. '1m', '5m', '10m').
    existing_strategies : list[dict]
        A list of currently accepted strategy summaries to enforce uniqueness.
    round_num : int
        The current round in the generation pipeline.
    total_rounds : int
        The total number of strategies being generated.
    market_regime : str, default "High Volatility, Sideways"
        Market environment description.
    investment_thesis : str, default "Exploit asymmetric skewness in order flow."
        Financial thesis to test.
    experience : str, default ""
        Combat experience log text to enforce rules and prevent repeated bugs.
    tried_names : list[str], optional
        List of names that have failed to compile previously.
    fsa_forbidden_patterns : list[str], optional
        List of root topology structures that should not be repeated.
        
    Returns
    -------
    str
        The fully formatted prompt string.
    """
    
    # Context sections
    existing_section = ""
    if existing_strategies:
        existing_list = "\n".join([f"  - [{s.get('timeframe', '10m')}] {s.get('name', 'Strategy')} ({s.get('family', s.get('template_name', 'unknown'))})" for s in existing_strategies])
        existing_section = f"## ALREADY ACCEPTED STRATEGIES (MUST BE UNIQUE)\n{existing_list}\n"
    else:
        existing_section = "## ALREADY ACCEPTED STRATEGIES\n(None yet. This is the first strategy.)\n"
        
    tried_section = ""
    if tried_names:
        tried_list = ", ".join(sorted(tried_names))
        tried_section = f"## PREVIOUSLY TRIED & FAILED NAMES\n{tried_list}\n"

    used_families = [s.get('family', '') for s in existing_strategies]
    unused_families = [f for f in STRATEGY_FAMILIES if f not in used_families]
    suggested = f"Suggested unused families: **{', '.join(unused_families[:3])}**" if unused_families else "All families used. Create a unique variation."

    tf_hint = TIMEFRAME_HINTS.get(timeframe, "")
    if experience:
        exp_section = f"## COMBAT EXPERIENCE (MANDATORY TO FOLLOW)\n{experience}\n"
    else:
        exp_section = "## COMBAT EXPERIENCE\n(No experience log is available.)\n"
    
    fsa_section = ""
    if fsa_forbidden_patterns:
        fsa_list = ", ".join(fsa_forbidden_patterns)
        fsa_section = f"\nCRITICAL CONSTRAINT: Do not generate blueprints that share the exact structural topology as the following root patterns: {fsa_list}\n"

    few_shot = "\n".join(
        f"- Example {i} ({family}): `{blueprint}`"
        for i, (family, blueprint) in enumerate(FEW_SHOT_EXAMPLES, start=1)
    )

    static_prefix = f"""You are an expert **Quant Researcher** designing trading strategies for the **VN30 Index Futures contract**.

## REFERENCE LIBRARY
{DIMENSIONAL_FUNCTIONS}
{OPERATOR_FUNCTIONS}

## OUTPUT FORMAT
You MUST return EXACTLY the following JSON structure. 

```json
{{
    "name": "StrategyName",
    "timeframe": "10m",
    "family": "statistical-mean-reversion|time-series-kinematics|volatility-regime|cross-dimensional-arbitrage",
    "description": "Financial intuition behind the strategy.",
    "macro_blueprint": "sub(ts_mean(?), ts_mean(?))"
}}
```

**Few-Shot Examples for macro_blueprint:**
{few_shot}

## CRITICAL RULES (MUST FOLLOW STRICTLY)
1. **ROOT TYPE**: The root (outermost function) decides how positions are built.
   - Prefer a root whose output keeps its input dimension: `sub`, `add`, `mult`, `ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_argmax`, `ts_argmin`. The engine applies a rolling Z-Score to it and trades when |Z| exceeds a searched threshold.
   - A BOOLEAN root (`greater_than`, `less_than`, `equal`, `and_`, `or_`, `not_`) is also fine: long where true, short where false.
   - AVOID a RATIO root (`div`, `ts_rank`, `ts_corr`, `ts_zscore`): it is read as a 0-100 oscillator (long above 60-80, short below 20-40), which does not fit these outputs.
2. **Valid Functions ONLY**: RESTRICT YOURSELF EXCLUSIVELY to the exact names listed in the REFERENCE LIBRARY. Do not invent indicators (no `ema`, `rsi`, `macd`, `zscore`, `diff`, `shift`).
3. **No Hardcoded Numbers**: Window lengths and thresholds are searched by the engine. Keep NO numbers in the blueprint.
4. **Syntax & Depth Limit**: DO NOT nest functions deeper than 3 levels. Ensure all parentheses are closed. Use `?` (or a data field name) for each series argument and never for a window: `ts_mean(?)` is correct, `ts_mean(?, ?)` is wrong, `ts_mean(?, 20)` is wrong.
5. **JSON Only**: OUTPUT ONLY a valid JSON block.
"""

    dynamic_suffix = f"""
## CURRENT MISSION & MARKET CONTEXT
- Task: Design 1 intraday trading strategy for the **{timeframe}** timeframe.
- Round: {round_num}/{total_rounds}
- **Market Regime**: {market_regime}
- **Investment Thesis**: {investment_thesis}
- Family Recommendation: {suggested}

{tf_hint}

{existing_section}
{tried_section}
{fsa_section}
{exp_section}

GIVE ME THE JSON NOW:
"""
    return static_prefix + dynamic_suffix

def build_correction_prompt(failed_json_part_str: str, error_traceback: str) -> str:
    """
    Build a self-correction prompt for the LLM when validation/compilation fails.
    
    Provides the LLM with the invalid part of the strategy JSON and the error traceback
    from the compiler sandbox, urging it to resolve the syntax or logic violation.

    Parameters
    ----------
    failed_json_part_str : str
        The JSON fragment or parameter subset that caused the failure.
    error_traceback : str
        The error traceback message raised by the compiler sandbox.

    Returns
    -------
    str
        The formatted correction prompt string.
    """
    return f"""Your previous generated strategy JSON failed execution validation in our sandbox.

Here is the specific part of the JSON that caused the error:
```json
{failed_json_part_str}
```

Here is the error traceback from the sandbox:
```
{error_traceback}
```

CRITICAL RULES FOR CORRECTION:
1. Identify the source of the error in your formulas or parameter space.
   - For example: syntax errors, unknown function names, wrong number of series arguments (`ts_mean(?)` takes one, `ts_corr(?, ?)` takes two), numbers written into the blueprint, mixing price and volume in one `add`/`sub`/comparison, or a BOOLEAN function fed with a non-BOOLEAN argument.
2. Fix the errors while preserving the core trading concept.
3. Return ONLY a valid JSON block containing the corrected fields. Do not return the entire original JSON. Do not include any explanations or commentary.
"""
