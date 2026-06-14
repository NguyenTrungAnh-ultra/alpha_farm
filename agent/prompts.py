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
TALIB_INDICATORS = """
## Available Indicators (called via self.feat.xxx())

**Trend**: sma, ema, dema, tema, wma, kama, t3, trima, midpoint, midprice, sar, linearreg, linearreg_slope
**Momentum**: rsi, stoch, stochf, stochrsi, macd, mom, roc, rocp, willr, cci, cmo, mfi, ultosc, trix, adx, adxr, aroon, aroonosc, dx, minus_di, plus_di, apo, ppo, bop
**Volatility**: atr, natr, trange, bbands (upper/middle/lower)
**Volume**: ad, adosc, obv, cmf, rolling_vwap
**Pattern (Use EXACT names below, DO NOT use cdl_ prefix)**: piercing_pattern, engulfing_pattern, harami_pattern, harami_cross_pattern, hikkake_pattern, modified_hikkake_pattern, in_neck_pattern, on_neck_pattern
**Math**: max, min, stddev, linearreg_angle
**Advanced/Statistical**: rolling_zscore, rolling_mad, rolling_correlation, rolling_rank, log_returns
"""

# ─── Available operator functions ────────────────────────────────────────
OPERATOR_FUNCTIONS = """
## Available Operator Functions (called via self.op.xxx())

**Time Series**: shift, diff, pct_change
**Crossings**: crossed, crossed_above, crossed_below, crossed_above_value, crossed_below_value
**Rolling Math**: rolling_mean, rolling_max, rolling_min, rolling_std, rolling_sum
**Utility**: clip, fillna, ffill, abs, where, sign, isna, notna, isfinite, zero_ifna
"""

# ─── Timeframe-specific guidance ────────────────────────────────────
TIMEFRAME_HINTS = {
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
    experience: str = "",
    tried_names: list[str] = None,
) -> str:
    """
    Build prompt for generating a strategy idea (JSON).
    """
    
    # Context sections
    existing_section = ""
    if existing_strategies:
        existing_list = "\n".join([f"  - [{s['timeframe']}] {s['name']} ({s['family']})" for s in existing_strategies])
        existing_section = f"## 1. ALREADY ACCEPTED STRATEGIES (DO NOT DUPLICATE)\n{existing_list}\n"
    else:
        existing_section = "## 1. ALREADY ACCEPTED STRATEGIES\n(None yet. This is the first strategy.)\n"
        
    tried_section = ""
    if tried_names:
        tried_list = ", ".join(sorted(tried_names))
        tried_section = f"## 2. PREVIOUSLY TRIED & FAILED NAMES (DO NOT REUSE)\n{tried_list}\n"

    used_families = [s.get('family', '') for s in existing_strategies]
    unused_families = [f for f in STRATEGY_FAMILIES if f not in used_families]
    suggested = f"Suggested unused families: **{', '.join(unused_families[:3])}**" if unused_families else "All families used. Create a unique variation."

    tf_hint = TIMEFRAME_HINTS.get(timeframe, "")
    exp_section = f"## 3. COMBAT EXPERIENCE (MANDATORY)\n{experience}\n" if experience else ""

    return f"""You are an expert **Quant Researcher** designing trading strategies for the **VN30 Index Futures contract** (Vietnamese market derivatives).

## Task
Design 1 intraday trading strategy for the **{timeframe}** timeframe.
This is round {round_num}/{total_rounds}.

{tf_hint}

{existing_section}
{tried_section}
{exp_section}
## 4. REFERENCE LIBRARY

{TALIB_INDICATORS}

{OPERATOR_FUNCTIONS}

## 5. CRITICAL RULES (MUST FOLLOW STRICTLY)
1. **Uniqueness**: Your strategy MUST be COMPLETELY DIFFERENT from the accepted ones above. Use different logic, different indicators, or a different family.
2. **Family**: {suggested}
3. **Logic Strictness**: You must have CLEAR entry and exit logic, expressed strictly as Python mathematical formulas. NO natural language.
4. **Complexity**: Must use **at least 2 indicators** (1 primary + 1 filter/confirmation).
5. **Distinct Exits**: Must have its **own exit logic** (do not just reverse the entry signals).
6. **Valid Functions ONLY**: You are ONLY allowed to use the indicators and operators listed in the "REFERENCE LIBRARY" above via `self.feat.xxx()` or `self.op.xxx()`. Do NOT invent any functions. Do NOT use Pandas methods like `.rolling()` or `.shift()`.
7. **Pandas Bitwise Logic**: You MUST use Pandas bitwise operators `&`, `|`, `~` for logical conditions instead of `and`, `or`, `not`. You MUST wrap every condition in parentheses. Example: `(close > MA) & (RSI < 30)`.

## 6. OUTPUT FORMAT

You MUST return EXACTLY the following JSON structure. Do not add any text outside the JSON block.

```json
{{
    "name": "StrategyName",
    "timeframe": "{timeframe}",
    "family": "trend-following|momentum|mean-reversion|breakout|volatility|multi-indicator|pattern-based|channel|oscillator-divergence|session-based",
    "description": "Brief description of the strategy logic.",
    "formula": {{
        "inputs": ["close", "high", "low", "open_price", "volume"],
        "indicators": [
            {{"name": "EMA_fast", "definition": "self.feat.ema(close, timeperiod=10)"}},
            {{"name": "ATR", "definition": "self.feat.atr(high, low, close, timeperiod=14)"}}
        ],
        "entry_long": "(close > EMA_fast) & (ATR > 0.5)",
        "entry_short": "(close < EMA_fast) & (ATR > 0.5)",
        "exit_long": "(close < EMA_fast)",
        "exit_short": "(close > EMA_fast)"
    }},
    "param_space": {{
        "param_name": {{"type": "int|float", "low": 5, "high": 30, "step": 1}},
        "another_param": {{"type": "float", "low": 0.5, "high": 3.0, "step": 0.1}}
    }}
}}
```"""

