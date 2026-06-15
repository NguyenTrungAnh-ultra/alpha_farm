"""
Prompt Templates for Template-Based Strategy Generation (XNO Engine)
=====================================================================
Prompts that produce XNOQuant-compatible strategies using pre-defined Templates.
"""

from agent.templates import TEMPLATE_REGISTRY

# ─── Timeframe-specific guidance ────────────────────────────────────
TIMEFRAME_HINTS = {
    "10m": """
**10-Minute Timeframe** — Balanced Intraday:
- Trades: 2-5/day
- Suitable for: Trend confirmation, multi-indicator systems
- Stop loss: 5-10 points
""",
    "15m": """
**15-Minute Timeframe** — Swing Intraday:
- Trades: 1-3/day
- Suitable for: High-quality trend-following, divergence, pattern recognition
- Stop loss: 8-15 points
- Fewer signals but much higher quality
""",
    "30m": """
**30-Minute Timeframe** — Position Intraday:
- Trades: 0-2/day (some days may have no trades)
- Suitable for: Major trends, range breakouts, session-based strategies
- Stop loss: 10-20 points
- Caution: Fewer bars per day, so indicators need sufficient lookback
""",
    "60m": """
**1-Hour Timeframe** — Position/Large Swing:
- Trades: 0-1/day (very rare, some weeks may have no trades)
- Suitable for: Major trend following, regime detection
- Stop loss: 15-30 points
- Requires appropriate indicator periods (only ~5 bars per day)
""",
}

def get_templates_help_text() -> str:
    lines = []
    lines.append("## Available Strategy Templates")
    for name, info in TEMPLATE_REGISTRY.items():
        lines.append(f"- **{name}**: {info['description']}")
        lines.append("  Allowed parameters and bounds (You MUST pick values strictly within these ranges):")
        for p_name, p_info in info['params'].items():
            lines.append(f"    - `{p_name}` ({p_info['type']}): Min={p_info['low']}, Max={p_info['high']} (default={p_info['default']})")
    return "\n".join(lines)

def build_idea_prompt(
    timeframe: str,
    existing_strategies: list[dict],
    round_num: int,
    total_rounds: int,
    experience: str = "",
    tried_names: list[str] = None,
    use_lite: bool = False,
) -> str:
    """
    Build prompt for generating a strategy idea (JSON) using template-based approach.
    """
    templates_help = get_templates_help_text()
    tf_hint = TIMEFRAME_HINTS.get(timeframe, "")

    existing_section = ""
    if existing_strategies:
        existing_list = "\n".join([f"  - [{s.get('timeframe')}] {s.get('name')} ({s.get('template_name', 'unknown')})" for s in existing_strategies])
        existing_section = f"## 1. ALREADY ACCEPTED STRATEGIES (DO NOT DUPLICATE NAMES)\n{existing_list}\n"
    else:
        existing_section = "## 1. ALREADY ACCEPTED STRATEGIES\n(None yet. This is the first strategy.)\n"

    tried_section = ""
    if tried_names:
        tried_list = ", ".join(sorted(tried_names))
        tried_section = f"## 2. PREVIOUSLY TRIED & FAILED NAMES (DO NOT REUSE)\n{tried_list}\n"

    if use_lite:
        # Lite Prompt for Local Model (Ollama)
        return f"""You are a Quant Researcher. Design 1 intraday trading strategy for VN30 Index Futures on **{timeframe}** timeframe.
This is round {round_num}/{total_rounds}.

{tf_hint}

{existing_section}
{tried_section}
{templates_help}

## CRITICAL RULES
1. You MUST select exactly ONE template from the list above.
2. You MUST specify parameter values strictly within their allowed Min and Max bounds.
3. The name MUST be unique and not in the list of tried/accepted names.
4. Output ONLY valid JSON in the format below. No markdown text outside the JSON block.

## OUTPUT FORMAT
```json
{{
    "name": "UniqueStrategyName",
    "timeframe": "{timeframe}",
    "template_name": "SelectedTemplateName",
    "rationale": "Brief rationale for selecting this template and these parameters",
    "parameters": {{
        "param_name": value
    }}
}}
```"""

    # Full Prompt for Big Model (Gemini/Deepseek)
    exp_section = f"## 3. COMBAT EXPERIENCE (MANDATORY)\n{experience}\n" if experience else ""

    return f"""You are an expert **Quant Researcher** designing trading strategies for the **VN30 Index Futures contract** (Vietnamese market derivatives).

## Task
Design 1 intraday trading strategy for the **{timeframe}** timeframe by choosing an optimal template and parameter set.
This is round {round_num}/{total_rounds}.

{tf_hint}

{existing_section}
{tried_section}
{exp_section}
{templates_help}

## CRITICAL RULES (MUST FOLLOW STRICTLY)
1. **Uniqueness**: Your strategy name and setup must be unique.
2. **Template Selection**: You MUST choose exactly ONE template from the "Available Strategy Templates" list.
3. **Parameter Integrity**: You MUST supply values for ALL parameters required by the selected template. The values MUST be strictly within the defined Min and Max bounds. Do NOT invent new parameters.
4. **Logic**: Choose parameters that align with VN30 index behaviors (mean-reverting vs trend-following based on your Combat Experience).

## OUTPUT FORMAT
You MUST return EXACTLY the following JSON structure. Do not add any text outside the JSON block.

```json
{{
    "name": "UniqueStrategyName",
    "timeframe": "{timeframe}",
    "template_name": "SelectedTemplateName",
    "rationale": "Detailed rationale based on market analysis and experience",
    "parameters": {{
        "param1": 15,
        "param2": 65.0
    }}
}}
```"""
