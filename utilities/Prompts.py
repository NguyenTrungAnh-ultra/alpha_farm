"""
Prompts
=======
Prompt templates and builders for the Alpha Farm strategy generation pipeline.

Maintains dictionaries of timeframe hints, the library of available data fields/operators, 
and helper functions to construct structured LLM prompts for generating strategy 
blueprints and self-correction instructions.
"""

import hashlib

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

# Wrong example is a complete formula (no slot); the tests check it is rejected.
SLOT_WRONG_EXAMPLE = "sub(ts_mean(pv_high), ts_mean(pv_low))"
SLOT_RIGHT_EXAMPLE = "sub(ts_mean(?), ts_mean(?))"

SLOT_RULES = f"""
## WHAT `?` MEANS (READ FIRST)
`?` is an OPEN SLOT. You write only the SKELETON of the formula; the search later fills every `?` with a data field or a whole sub-formula.
- EVERY blueprint MUST contain at least one `?` (prefer 2 or 3). A blueprint with no `?` is REJECTED.
- Data fields such as `pv_close` or `pv_volume` may appear in the skeleton, but the parts you leave open MUST be `?`.
- WRONG (complete formula, no `?`, rejected): `{SLOT_WRONG_EXAMPLE}`
- RIGHT (same skeleton with open slots): `{SLOT_RIGHT_EXAMPLE}`
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


_OUTDATED_DIMENSION_LINE = (
    "  - `ts_rank`, `ts_corr`, `ts_zscore` return a dimensionless RATIO. The others keep the dimension of their input.\n"
)

# Anonymised variants: the shared OPERATOR_FUNCTIONS text minus its dimension line, plus rules that
# match what the compiler enforces. `current` keeps OPERATOR_FUNCTIONS unchanged (pinned hash).
DIMENSION_RULES = """**Dimensions** (every series has one: CURRENCY for price fields, VOLUME for `pv_volume`, or RATIO = dimensionless; the blueprint is REJECTED if they do not fit):
  - `ts_mean`, `ts_sum`, `ts_max`, `ts_min` keep the dimension of their input.
  - `ts_rank`, `ts_zscore`, `ts_argmax`, `ts_argmin`, `ts_corr` always return a RATIO, whatever their input.
  - `add`, `sub`, `greater_than`, `less_than`, `equal`: both sides MUST have the same dimension (price with price, volume with volume, ratio with ratio).
  - `mult`: at least one side MUST be a RATIO (result has the other side's dimension). Price x volume, price x price and volume x volume are REJECTED. To weight a non-RATIO series, pair it with a side whose dimension is RATIO (see the dimension list above).
  - `div`: both sides have the same dimension (result is a RATIO), or the divisor is a RATIO (result keeps the numerator's dimension).
  - Every `?` must be fillable within the depth limit: a `?` that has to be a RATIO inside a rolling function (for example both arguments of a `sub` that sits under `mult`) needs an extra nesting level there. Keep such skeletons shallow and simple.
"""
ANON_OPERATOR_FUNCTIONS = OPERATOR_FUNCTIONS.replace(_OUTDATED_DIMENSION_LINE, "") + DIMENSION_RULES

# Every example must compile with SemanticCompiler (checked by tests).
FEW_SHOT_EXAMPLES = [
    ("statistical-mean-reversion", "sub(ts_max(?), ts_mean(?))"),
    ("time-series-kinematics", "sub(ts_mean(?), ts_mean(?))"),
    ("volatility-regime", "sub(ts_max(pv_high), ts_min(?))"),
    ("cross-dimensional-arbitrage", "mult(ts_zscore(?), ts_corr(pv_volume, ?))"),
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

CRITICAL_RULES = """## CRITICAL RULES (MUST FOLLOW STRICTLY)
1. **ROOT TYPE**: The root (outermost function) decides how positions are built.
   - Prefer a root whose output keeps its input dimension: `sub`, `add`, `mult`, `ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_argmax`, `ts_argmin`. The engine applies a rolling Z-Score to it and trades when |Z| exceeds a searched threshold.
   - A BOOLEAN root (`greater_than`, `less_than`, `equal`, `and_`, `or_`, `not_`) is also fine: long where true, short where false.
   - AVOID a RATIO root (`div`, `ts_rank`, `ts_corr`, `ts_zscore`): it is read as a 0-100 oscillator (long above 60-80, short below 20-40), which does not fit these outputs.
2. **Valid Functions ONLY**: RESTRICT YOURSELF EXCLUSIVELY to the exact names listed in the REFERENCE LIBRARY. Do not invent indicators (no `ema`, `rsi`, `macd`, `zscore`, `diff`, `shift`).
3. **No Hardcoded Numbers**: Window lengths and thresholds are searched by the engine. Keep NO numbers in the blueprint.
4. **Syntax & Depth Limit**: DO NOT nest functions deeper than 3 levels. Ensure all parentheses are closed. Use `?` for each open series argument (a data field name only where you fix it on purpose) and never for a window: `ts_mean(?)` is correct, `ts_mean(?, ?)` is wrong, `ts_mean(?, 20)` is wrong.
5. **At least one `?`** in `macro_blueprint` (see WHAT `?` MEANS).
6. **JSON Only**: OUTPUT ONLY a valid JSON block.
"""

# ─── Prompt variants (static part of the idea prompt) ───────────────

# Skeletons the library text itself illustrates syntax with (`ts_mean(?)`, `ts_corr(?, ?)`).
LIBRARY_ILLUSTRATIONS = ["ts_mean(?)", "ts_corr(?, ?)"]

# Slot rules without any concrete formula: used by the market-anonymised variants.
SLOT_RULES_PLAIN = """
## WHAT `?` MEANS (READ FIRST)
`?` is an OPEN SLOT. You write only the SKELETON of the formula; the search later fills every `?` with a data field or a whole sub-formula.
- EVERY blueprint MUST contain at least one `?` (prefer 2 or 3). A blueprint with no `?` is REJECTED.
- Data fields such as `pv_close` or `pv_volume` may appear in the skeleton, but the parts you leave open MUST be `?`.
- WRONG: a complete formula in which every series argument is a named data field (no `?` anywhere). It is rejected.
- RIGHT: the same skeleton with `?` written in place of the series arguments you leave open.
"""

GRAMMAR_RULES = """
## GRAMMAR
blueprint := FUNCTION(argument, ...)
argument  := blueprint | DATA_FIELD | `?`
- Each function takes exactly the number of series arguments stated in the library above.
- Math functions take two arguments; BOOLEAN functions combine or compare series; time-series functions take one series (`ts_corr` takes two).
- Compose the skeleton yourself from the library: pick the operators, the nesting and the positions of the `?` slots.
"""

# Structural shapes only: operator mixes that are unlikely final answers. Each must compile with a slot.
SHAPE_EXAMPLES = [
    "mult(ts_sum(?), ts_argmax(?))",
    "ts_argmin(ts_max(?))",
    "not_(greater_than(ts_argmin(?), ts_argmax(?)))",
    "or_(less_than(ts_min(?), ts_sum(?)), greater_than(ts_argmax(?), ts_argmin(?)))",
]

ANON_INTRO = (
    "You are an expert **Quant Researcher** designing trading strategies for an **index futures contract** "
    "traded on **60-minute bars**."
)

ANON_OUTPUT_FORMAT = """## OUTPUT FORMAT
You MUST return EXACTLY the following JSON structure.

```json
{
    "name": "StrategyName",
    "timeframe": "60m",
    "family": "statistical-mean-reversion|time-series-kinematics|volatility-regime|cross-dimensional-arbitrage",
    "description": "Financial intuition behind the strategy.",
    "macro_blueprint": "<your skeleton formula, built from the library, containing at least one ? slot>"
}
```
"""


def _current_static_prefix(timeframe: str) -> str:
    few_shot = "\n".join(
        f"- Example {i} ({family}): `{blueprint}`"
        for i, (family, blueprint) in enumerate(FEW_SHOT_EXAMPLES, start=1)
    )
    return f"""You are an expert **Quant Researcher** designing trading strategies for the **VN30 Index Futures contract**.

## REFERENCE LIBRARY
{DIMENSIONAL_FUNCTIONS}
{OPERATOR_FUNCTIONS}
{SLOT_RULES}
## OUTPUT FORMAT
You MUST return EXACTLY the following JSON structure. 

```json
{{
    "name": "StrategyName",
    "timeframe": "10m",
    "family": "statistical-mean-reversion|time-series-kinematics|volatility-regime|cross-dimensional-arbitrage",
    "description": "Financial intuition behind the strategy.",
    "macro_blueprint": "{SLOT_RIGHT_EXAMPLE}"
}}
```

**Examples for macro_blueprint (each contains `?`):**
{few_shot}

{CRITICAL_RULES}"""


def _anon_rules_static_prefix(timeframe: str) -> str:
    """Anonymised market, no formula example: grammar rules plus slot rules."""
    return f"""{ANON_INTRO}

## REFERENCE LIBRARY
{DIMENSIONAL_FUNCTIONS}
{ANON_OPERATOR_FUNCTIONS}
{SLOT_RULES_PLAIN}
{GRAMMAR_RULES}
{ANON_OUTPUT_FORMAT}
{CRITICAL_RULES}"""


def _anon_shapes_static_prefix(timeframe: str) -> str:
    """Anonymised market, structural shapes plus an explicit ban on reusing any of them."""
    shapes = "\n".join(f"- Shape {i}: `{shape}`" for i, shape in enumerate(SHAPE_EXAMPLES, start=1))
    return f"""{ANON_INTRO}

## REFERENCE LIBRARY
{DIMENSIONAL_FUNCTIONS}
{ANON_OPERATOR_FUNCTIONS}
{SLOT_RULES_PLAIN}
{GRAMMAR_RULES}
## SHAPES (GRAMMAR ILLUSTRATION ONLY)
These shapes only show how functions nest and where `?` goes. They are NOT suggestions.
{shapes}
NEVER output any of these shapes, and never output one of them with other data fields in place of the fixed ones. Any blueprint with the same skeleton as a shape above is REJECTED. Design a DIFFERENT skeleton of your own.

{ANON_OUTPUT_FORMAT}
{CRITICAL_RULES}"""


class PromptVariant:
    """A named static prompt: its builder and the skeletons it shows the model (a generated copy is rejected)."""

    def __init__(self, name: str, build_static, examples: list[str], anonymised: bool):
        self.name = name
        self.build_static = build_static
        self.examples = examples
        self.anonymised = anonymised


PROMPT_VARIANTS = {
    "current": PromptVariant(
        "current", _current_static_prefix,
        [blueprint for _, blueprint in FEW_SHOT_EXAMPLES] + [SLOT_RIGHT_EXAMPLE] + LIBRARY_ILLUSTRATIONS,
        anonymised=False),
    "anon_rules": PromptVariant("anon_rules", _anon_rules_static_prefix, list(LIBRARY_ILLUSTRATIONS), anonymised=True),
    "anon_shapes": PromptVariant(
        "anon_shapes", _anon_shapes_static_prefix, list(SHAPE_EXAMPLES) + LIBRARY_ILLUSTRATIONS, anonymised=True),
}


def get_variant(name: str) -> PromptVariant:
    if name not in PROMPT_VARIANTS:
        raise ValueError(f"Unknown prompt variant '{name}'; choose one of {sorted(PROMPT_VARIANTS)}")
    return PROMPT_VARIANTS[name]


def build_static_prefix(variant: str, timeframe: str = "60m") -> str:
    """Static part of the idea prompt for `variant`. The anonymised variants are written for 60-minute bars only."""
    chosen = get_variant(variant)
    if chosen.anonymised and timeframe != "60m":
        raise ValueError(f"Prompt variant '{variant}' is written for 60m bars, got {timeframe}")
    return chosen.build_static(timeframe)


def variant_examples(variant: str) -> list[str]:
    """Skeletons shown to the model by `variant`; a generated blueprint with one of these structures is a copy."""
    return list(get_variant(variant).examples)


def prompt_hash(variant: str) -> str:
    """sha256 of the static prompt text of `variant` for 60m bars."""
    return hashlib.sha256(build_static_prefix(variant).encode("utf-8")).hexdigest()


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
    variant: str = "current",
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
    variant : str, default "current"
        Name in `PROMPT_VARIANTS` selecting the static part of the prompt.
        
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

    static_prefix = build_static_prefix(variant, timeframe)

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
   - For example: syntax errors, unknown function names, wrong number of series arguments (`ts_mean(?)` takes one, `ts_corr(?, ?)` takes two), numbers written into the blueprint, mixing price and volume in one `add`/`sub`/comparison, or a BOOLEAN function fed with a non-BOOLEAN argument, or a blueprint with no `?` slot (it must contain at least one `?`: replace an open part by `?`).
2. Fix the errors while preserving the core trading concept.
3. Return ONLY a valid JSON block containing the corrected fields. Do not return the entire original JSON. Do not include any explanations or commentary.
"""


# ═══════════════════════════════════════════════════════════════════════
# Batched requests: several blueprints in one reply
# ═══════════════════════════════════════════════════════════════════════

BATCH_FORMAT_RULES = """## BATCH OUTPUT FORMAT (OVERRIDES THE SINGLE-OBJECT FORMAT ABOVE)
Return EXACTLY ONE JSON object with the key `ideas`, a list of {n} objects. Each element has the same fields as the OUTPUT FORMAT above (`name`, `timeframe`, `family`, `description`, `macro_blueprint`).
```json
{{"ideas": [{{"name": "...", "timeframe": "{timeframe}", "family": "...", "description": "...", "macro_blueprint": "..."}}, ...]}}
```
- Every `macro_blueprint` follows ALL the rules above (valid names only, at least one `?`, no numbers, nesting depth at most 3).
- The {n} skeletons MUST differ from each other in operators or nesting, and every `name` must be different.
"""


def _avoid_section(avoid: list[str]) -> str:
    if not avoid:
        return ""
    lines = "\n".join(f"  - `{text}`" for text in avoid)
    return (f"## SKELETONS ALREADY TAKEN (DO NOT REPEAT THEM OR THEIR STRUCTURE)\n{lines}\n"
            "A skeleton with the same operators and nesting as one above is REJECTED, even with other data fields.\n")


def build_batch_prompt(
    timeframe: str,
    n: int,
    avoid: list[str] = None,
    variant: str = "anon_shapes",
    experience: str = "",
    market_regime: str = "High Volatility, Sideways",
    investment_thesis: str = "Exploit asymmetric skewness in order flow.",
) -> str:
    """
    Prompt asking for `n` blueprints at once as `{"ideas": [...]}`. `avoid` lists blueprint texts that are already
    accepted, so the model does not repeat them. The static part is the one of `variant`.
    """
    static_prefix = build_static_prefix(variant, timeframe)
    exp_section = f"## COMBAT EXPERIENCE (MANDATORY TO FOLLOW)\n{experience}\n" if experience else ""
    return static_prefix + f"""
{BATCH_FORMAT_RULES.format(n=n, timeframe=timeframe)}
## CURRENT MISSION & MARKET CONTEXT
- Task: Design {n} DIFFERENT intraday trading strategies for the **{timeframe}** timeframe, all in this one reply.
- **Market Regime**: {market_regime}
- **Investment Thesis**: {investment_thesis}
- Cover several families: {', '.join(STRATEGY_FAMILIES)}.

{TIMEFRAME_HINTS.get(timeframe, "")}

{_avoid_section(avoid or [])}
{exp_section}
GIVE ME THE JSON NOW:
"""


def build_feedback_prompt(
    timeframe: str,
    n: int,
    scored: list[dict],
    avoid: list[str] = None,
    variant: str = "anon_shapes",
) -> str:
    """
    Prompt for the feedback round: `scored` holds the best formulas the search found so far, each a dict with
    `expression` (text), `reward` and `rank_ic`, all measured on the training segment. Nothing else about the
    data is shown (no market name, no later segment). The model is asked for `n` new blueprints in one reply.
    """
    static_prefix = build_static_prefix(variant, timeframe)
    lines = "\n".join(
        f"  {i}. `{item['expression']}`  reward {item['reward']:.4f}, rank IC {item['rank_ic']:+.4f}"
        for i, item in enumerate(scored, start=1)
    )
    return static_prefix + f"""
{BATCH_FORMAT_RULES.format(n=n, timeframe=timeframe)}
## FEEDBACK FROM THE SEARCH SO FAR
A search filled earlier skeletons with data fields and rolling windows and scored every complete formula on historical {timeframe} bars. These are the {len(scored)} best distinct formulas, best first. `reward` is the search score (higher is better); `rank IC` is the Spearman correlation between the formula and the next bar's return. Rolling windows are left out of the formulas on purpose: in a blueprint every `ts_*` operator takes only its series (one argument, `ts_corr` two) and you never write a window or any number.
{lines}

## CURRENT MISSION
- Task: Design {n} NEW skeletons that the search should try next, in this one reply. Learn from which operators, nestings and data fields scored well above, and also try neighbouring ideas that the formulas above do not cover.
- Every skeleton must contain at least one `?` and must differ in operators or nesting from each other and from the skeletons already taken.

{_avoid_section(avoid or [])}
GIVE ME THE JSON NOW:
"""


def build_batch_correction_prompt(failures: list[tuple[str, str]]) -> str:
    """
    One correction request for several rejected ideas: `failures` is a list of (macro_blueprint, error message).
    The reply is a JSON object `{"ideas": [...]}` with one corrected entry per failure, in the same order.
    """
    blocks = "\n".join(
        f"{i}. blueprint: `{blueprint}`\n   error: {error}" for i, (blueprint, error) in enumerate(failures, start=1)
    )
    return f"""Some of the strategy skeletons you just generated failed validation in our sandbox.

Failures, in order:
{blocks}

CRITICAL RULES FOR CORRECTION:
1. Fix each skeleton so that it passes while keeping its trading idea. Typical causes: unknown function names, a wrong number of series arguments (`ts_mean(?)` takes one, `ts_corr(?, ?)` takes two; a window is never an argument), numbers written into the blueprint, mixing price and volume in one `add`/`sub`/comparison, a BOOLEAN function fed with a non-BOOLEAN argument, no `?` slot, or a structure equal to one that is already taken (then change the operators or the nesting).
2. Return ONLY one JSON object `{{"ideas": [...]}}` with exactly {len(failures)} objects, in the same order as above. Each object has the single field `macro_blueprint` holding the corrected skeleton. No explanations.
"""


# ═══════════════════════════════════════════════════════════════════════
# Complete formulas (the LLM-only configuration): no `?`, every window written out
# ═══════════════════════════════════════════════════════════════════════

# The dimension rules minus their last bullet, which is about `?` slots.
FORMULA_DIMENSION_RULES = "\n".join(DIMENSION_RULES.rstrip("\n").split("\n")[:-1]).replace(
    "the blueprint is REJECTED", "the formula is REJECTED")
assert "`?`" not in FORMULA_DIMENSION_RULES

# Syntax illustrations shown to the model; a reply equal to one of them is rejected as a copy.
FORMULA_EXAMPLES = [
    "ts_mean(pv_close, 5)",
    "sub(pv_high, ts_min(pv_low, 3))",
    "ts_corr(pv_open, pv_volume, 10)",
]


def _formula_prefix(windows: list[int]) -> str:
    shown = ", ".join(str(w) for w in windows)
    examples = "\n".join(f"- `{text}`" for text in FORMULA_EXAMPLES)
    return f"""{ANON_INTRO}

## REFERENCE LIBRARY
## Available Data Fields
{', '.join(DATA_FIELDS)}

## Available Operator Functions
**Time-Series** (rolling window): {_operator_names(OperatorGroup.TIME_SERIES)}
  - Each takes its series argument(s) first and ONE integer window LAST: `ts_mean(pv_close, 5)`; `ts_corr` takes two series, then the window: `ts_corr(pv_close, pv_volume, 5)`.
  - The window MUST be one of: {shown}. No other number may appear anywhere in the formula.
**Math** (two series arguments): {_operator_names(OperatorGroup.STATISTICS)}
**Logic**: {_operator_names(OperatorGroup.LOGIC)}
  - `and_`, `or_`, `not_` take BOOLEAN arguments; `greater_than`, `less_than`, `equal` take two series and return BOOLEAN.
{FORMULA_DIMENSION_RULES}
## WHAT A FORMULA IS
A COMPLETE formula: every series argument is a data field or another function call. There is NO `?` and no open slot; the search tunes only the trading thresholds afterwards.
formula  := FUNCTION(argument, ...)
argument := formula | DATA_FIELD
## SYNTAX ILLUSTRATIONS (NOT SUGGESTIONS)
{examples}
NEVER output one of these exactly. Design formulas of your own.

## CRITICAL RULES (MUST FOLLOW STRICTLY)
1. **Root**: prefer a root whose output keeps its input dimension (`sub`, `add`, `mult`, `ts_mean`, `ts_sum`, `ts_max`, `ts_min`, `ts_argmax`, `ts_argmin`); a BOOLEAN root (`greater_than`, `less_than`, `equal`, `and_`, `or_`, `not_`) is also fine. AVOID a RATIO root (`div`, `ts_rank`, `ts_corr`, `ts_zscore`).
2. **Valid names ONLY**: exactly the names above; do not invent indicators (no `ema`, `rsi`, `macd`, `zscore`, `diff`, `shift`).
3. **Windows**: the last argument of every time-series function, one of {shown}; no other numbers.
4. **Depth**: DO NOT nest functions deeper than 3 levels. Close all parentheses.
5. **JSON only**."""


def _formula_taken(avoid: list[str]) -> str:
    if not avoid:
        return ""
    lines = "\n".join(f"  - `{text}`" for text in avoid)
    return f"## FORMULAS ALREADY TAKEN (DO NOT REPEAT THEM EXACTLY)\n{lines}\n"


def build_formula_batch_prompt(timeframe: str, n: int, windows: list[int], avoid: list[str] = None) -> str:
    """
    Prompt asking for `n` complete formulas at once as `{"ideas": [{"name", "family", "description", "formula"}]}`.
    No market name, no data. `windows` are the rolling windows the engine offers at `timeframe` (the only numbers
    allowed); `avoid` lists the formulas already accepted.
    """
    if timeframe != "60m":
        raise ValueError(f"The formula prompt is written for 60m bars, got {timeframe}")
    return _formula_prefix(windows) + f"""

## BATCH OUTPUT FORMAT
Return EXACTLY ONE JSON object with the key `ideas`, a list of {n} objects with the fields `name`, `family`, `description`, `formula`.
```json
{{"ideas": [{{"name": "...", "family": "...", "description": "...", "formula": "..."}}, ...]}}
```
- The {n} formulas MUST be different from each other and every `name` must be different.

## CURRENT MISSION
- Task: Design {n} DIFFERENT complete trading formulas for the **{timeframe}** timeframe of an index futures contract, all in this one reply.
- Cover several families: {', '.join(STRATEGY_FAMILIES)}.

{_formula_taken(avoid or [])}
GIVE ME THE JSON NOW:
"""


def build_formula_correction_prompt(failures: list[tuple[str, str]], windows: list[int]) -> str:
    """One correction request for several rejected formulas: `failures` is a list of (formula, error message)."""
    shown = ", ".join(str(w) for w in windows)
    blocks = "\n".join(f"{i}. formula: `{text}`\n   error: {error}" for i, (text, error) in enumerate(failures, start=1))
    return f"""Some of the formulas you just generated failed validation in our sandbox.

Failures, in order:
{blocks}

CRITICAL RULES FOR CORRECTION:
1. Fix each formula so that it passes while keeping its trading idea. Typical causes: unknown function names, a wrong number of series arguments, a missing or disallowed window (the window is the LAST argument of every time-series function and must be one of {shown}), any other number, a `?`, mixing price and volume in one `add`/`sub`/comparison, nesting deeper than 3 levels, or a formula equal to one that is already taken.
2. Return ONLY one JSON object `{{"ideas": [...]}}` with exactly {len(failures)} objects, in the same order as above. Each object has the single field `formula` holding the corrected formula. No explanations.
"""
