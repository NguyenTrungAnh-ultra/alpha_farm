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

# ─── Available talib indicators (curated for futures) ────────────────
TALIB_INDICATORS = """
## Available talib Indicators (called via self.feat.xxx())

**Trend**: sma, ema, dema, tema, wma, kama, t3, trima, midpoint, midprice, sar, linearreg, linearreg_slope
**Momentum**: rsi, stoch, stochf, stochrsi, macd, mom, roc, rocp, willr, cci, cmo, mfi, ultosc, trix, adx, adxr, aroon, aroonosc, dx, minus_di, plus_di, apo, ppo, bop
**Volatility**: atr, natr, trange, bbands (upper/middle/lower)
**Volume**: ad, adosc, obv
**Pattern**: CDL functions (cdl_engulfing, cdl_hammer, cdl_doji, etc.)
**Math**: max, min, stddev, var, linearreg_angle
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
    
    # Format existing strategies list
    if existing_strategies:
        existing_list = "\n".join([
            f"  - [{s['timeframe']}] {s['name']} ({s['family']})"
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

    tf_hint = TIMEFRAME_HINTS.get(timeframe, "")

    exp_section = f"\n## COMBAT EXPERIENCE (MANDATORY READING)\n{experience}\n" if experience else ""

    return f"""You are an expert **Quant Researcher** designing trading strategies for the **VN30F1M futures contract** (VN30 index derivatives on the Vietnamese market).

## Task
Design 1 intraday trading strategy for the **{timeframe}** timeframe.
This is round {round_num}/{total_rounds}.

{tf_hint}
{exp_section}
## Quality Requirements
- The strategy must have **CLEAR entry/exit logic**, expressed strictly as mathematical formulas. NO natural language.
- Must use **at least 2 indicators** (1 primary + 1 filter/confirmation).
- Must have its **own exit logic** (do not just reverse signals).
- Parameters must have **reasonable search spaces** for optimization.
- Must be **COMPLETELY DIFFERENT** from existing strategies.
- **CRITICAL**: Use Pandas bitwise operators `&`, `|`, `~` for logic instead of `and`, `or`, `not`. You MUST wrap every condition in parentheses, e.g., `(close > MA) & (RSI < 30)`.
- **CRITICAL**: ONLY use the indicators listed below via `self.feat.xxx()`. Do not invent functions like `shift()`, `cumulative_sum()`, or `.rolling()`.

{existing_section}

{tried_section}

{suggested}

{TALIB_INDICATORS}

## Output Format — MUST return EXACT JSON structure below:

```json
{{
    "name": "StrategyName",
    "timeframe": "{timeframe}",
    "family": "trend-following|momentum|mean-reversion|breakout|volatility|multi-indicator|pattern-based|channel|oscillator-divergence|session-based",
    "description": "Brief description of the strategy logic",
    "formula": {{
        "inputs": ["close", "high", "low", "volume"],
        "indicators": [
            {{"name": "EMA_fast", "definition": "self.feat.ema(close, timeperiod=10)"}},
            {{"name": "ATR", "definition": "self.feat.atr(high, low, close, timeperiod=14)"}}
        ],
        "entry_long": "Specific mathematical formula to enter LONG (e.g.: (close > EMA_fast) & (ATR > 0.5))",
        "entry_short": "Specific mathematical formula to enter SHORT",
        "exit_logic": "Exit Long: [strict python formula]. Exit Short: [strict python formula]."
    }},
    "param_space": {{
        "param_name": {{"type": "int|float", "low": 5, "high": 30, "step": 1}},
        "another_param": {{"type": "float", "low": 0.5, "high": 3.0, "step": 0.1}}
    }}
}}
```

IMPORTANT: Return ONLY valid JSON. Do not add any text outside the JSON block."""

