"""
Prompt Templates for Strategy Generation (XNO Engine)
======================================================
Prompts that produce XNOQuant-compatible strategies using SimpleAlgorithm.

Design principles:
    - Self-contained: each prompt includes ALL context needed
    - Structured output: always request JSON/code in specific format
    - Domain-aware: VN30F1M futures specifics baked in
    - Timeframe-adaptive: different guidance per timeframe
    - Diversity-enforcing: explicit list of existing strategies
"""

# ─── Available talib & SDK indicators (curated for futures) ────────────────
DIMENSIONAL_FUNCTIONS = """
## Available Indicators (called via self.feat.xxx())

**[CURRENCY_OUTPUT_FUNCTIONS]**: ema, vwap, macd_line, stddev
**[RATIO_OUTPUT_FUNCTIONS]**: rsi, adx, roc, pct_change, stoch, var, zscore
**[CANDLESTICK_FUNCTIONS]**: doji, hammer, three_black_crows, morning_star
"""

# ─── Available operator functions ────────────────────────────────────────
OPERATOR_FUNCTIONS = """
## Available Operator Functions

**Time-Series**: shift, diff, pct_change
**[BOOLEAN_OUTPUT_FUNCTIONS]**: crossed, crossed_above, crossed_below, rising, falling, and_, or_, not_, greater_than, less_than
**Math**: add, sub, mult, div
**Statistics**: stddev, var, zscore
"""

# ─── Timeframe-specific guidance ────────────────────────────────────
TIMEFRAME_HINTS = {
    "1m": """
**1-Minute Timeframe** — Ultra Fast Scalping:
- Indicator periods: short-to-medium (5-20 bars)
- Trades: 10-30/day (high frequency)
- Suitable for: Fast momentum, micro-breakouts
- Stop loss: 1-3 points
- Extremely noisy. Needs very strong noise filters (e.g. volume or ADX confirmation).
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

# ─── Strategy families for diversity ────────────────────────────────
STRATEGY_FAMILIES = [
    "trend-following",      # EMA crossover, ADX filter, SAR, DEMA
    "momentum",             # RSI, MACD, Stochastic, TRIX, ROC
    "mean-reversion",       # Bollinger Bands, RSI extremes, CCI
    "breakout",             # Donchian, Keltner, range breakout, volatility breakout
    "volatility",           # ATR-based, Bollinger squeeze, volatility regime
    "multi-indicator",      # Combining 2-3 uncorrelated indicators
    "pattern-based",        # Candlestick patterns + confirmation
    "channel",              # Linear regression channel, price channel
    "oscillator-divergence",# RSI/MACD divergence, hidden divergence
    "session-based",        # Opening range breakout, session momentum
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
    Build prompt for generating a strategy idea (JSON).
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
    exp_section = f"## COMBAT EXPERIENCE (MANDATORY TO FOLLOW)\n{experience}\n" if experience else ""
    
    fsa_section = ""
    if fsa_forbidden_patterns:
        fsa_list = ", ".join(fsa_forbidden_patterns)
        fsa_section = f"\nCRITICAL CONSTRAINT: Do not generate blueprints that share the exact structural topology as the following root patterns: {fsa_list}\n"

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
    "family": "momentum|mean-reversion|volatility|statistical-arbitrage",
    "description": "Financial intuition behind the strategy.",
    "macro_blueprint": "div(macd_line(?), stddev(?))"
}}
```

**Few-Shot Examples for macro_blueprint:**
- Example 1 (Statistical Ratio): `div(sub(vwap(), ema(?)), stddev(?))`
- Example 2 (Z-Score Normalization): `zscore(roc(?))`
- Example 3 (Volatility Adjusted): `div(mult(rsi(?), var(?)), stddev(?))`

## CRITICAL RULES (MUST FOLLOW STRICTLY)
1. **CONTINUOUS SIGNAL ROOT**: The root (outermost function) of your macro_blueprint MUST evaluate to a RATIO or CURRENCY (e.g., div, zscore, rsi, pct_change). DO NOT use functions that output Dimension.ANY (such as add, sub, mult, ema, stddev) or BOOLEAN functions (like crossed_above, and_) as the final root.
2. **Valid Functions ONLY**: RESTRICT YOURSELF EXCLUSIVELY to the exact names listed in the REFERENCE LIBRARY.
3. **No Hardcoded Numbers**: REPLACE ALL numerical parameters with `?` (e.g., `ema(?)`). Keep NO hardcoded numbers.
4. **Syntax & Depth Limit**: DO NOT nest functions deeper than 3 levels. Ensure all parentheses are closed. Only use `?` for the main data series arguments, DO NOT pass `?` for constant parameters like timeperiod. For example, `ema(?)` is correct, `ema(?, ?)` is wrong.
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
    Build prompt for self-correction when a generated strategy fails validation.
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
   - For example: syntax errors, incorrect TA-Lib function parameter names (e.g. `period` instead of `timeperiod`), missing required parameters, dividing by zero/volume without offset, or using unallowed functions.
2. Fix the errors while preserving the core trading concept.
3. Return ONLY a valid JSON block containing the corrected fields. Do not return the entire original JSON. Do not include any explanations or commentary.
"""
