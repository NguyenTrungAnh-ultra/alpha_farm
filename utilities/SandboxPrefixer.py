"""
SandboxPrefixer
===============
Deterministic pre-processing layer — Tier 1 (Syntax) & Tier 2a (API/NameError).

Applies deterministic fixes (without LLM calls) on Python code generated from JSON,
then synchronizes the changes back to the JSON idea.

Flow:
    apply_prefixes(code, idea)
        ├── _apply_regex_rules()      → fix NameError, incorrect prefix, logical operator
        ├── _fix_unknown_feat_calls() → fuzzy "did you mean" matches on feature whitelist
        ├── _fix_json_fields()        → synchronize fixes back to the idea dict
        └── _check_ast_syntax()       → verify valid AST syntax after fixes
"""

import re
import ast
import copy
import os
from difflib import get_close_matches
from typing import Any


# ── Feature whitelist ──────────────────────────────────────────────────────

def _load_feat_whitelist() -> set[str]:
    """
    Load list of allowed features for self.feat.* from feature.txt or a hardcoded fallback.
    
    Returns
    -------
    set[str]
        A set of lowercase function names whitelisted.
    """
    whitelist: set[str] = set()
    possible_paths = [
        "f:/Projects/alpha_farm/feature.txt",
        os.path.join(os.path.dirname(__file__), "..", "feature.txt"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                matches = re.findall(r"self\.feat\.([a-zA-Z0-9_]+)\s*\(", content)
                for m in matches:
                    whitelist.add(m.lower())
            except Exception:
                pass
            if whitelist:
                break

    if not whitelist:
        whitelist = {
            "adx", "sma", "macd", "roc", "rsi", "obv", "vwap", "rolling_vwap", "bbands",
            "dema", "ema", "wma", "kama", "tema", "t3", "trima", "stddev", "var", "mom",
            "cmo", "cci", "mfi", "willr", "ultosc", "trix", "adxr", "aroon", "aroonosc",
            "dx", "minus_di", "plus_di", "apo", "ppo", "bop", "atr", "natr", "trange",
            "ad", "adosc", "linearreg", "linearreg_slope", "linearreg_angle", "midpoint",
            "midprice", "sar", "stoch", "stochf", "stochrsi", "max", "min", "rolling_mean",
            "rolling_sum", "rolling_std", "rolling_max", "rolling_min", "rolling_median",
            "rolling_quantile", "rolling_mad", "rolling_argmax", "rolling_argmin",
            "rolling_rank", "rolling_percentile_rank", "rolling_covariance",
            "rolling_correlation", "rolling_zscore", "price_z", "volume_z", "zscore",
            "returns", "log_returns", "donchian_upper", "donchian_lower", "hlc3", "ohlc4",
            "cmf", "minmax", "piercing_pattern", "engulfing_pattern", "harami_pattern",
            "harami_cross_pattern", "hikkake_pattern", "modified_hikkake_pattern",
            "in_neck_pattern", "on_neck_pattern",
        }
    return whitelist


FEAT_WHITELIST: set[str] = _load_feat_whitelist()

# Tập hàm self.op.* hợp lệ
OP_WHITELIST: set[str] = {
    "shift", "diff", "pct_change",
    "crossed", "crossed_above", "crossed_below", "crossed_above_value", "crossed_below_value",
    "clip", "fillna", "ffill", "abs", "where", "sign", "isna", "notna",
    "isfinite", "zero_ifna", "between", "value_when", "replace",
}


# ── Deterministic regex rules ──────────────────────────────────────────────
# Format: (pattern_str, replacement, rule_id, description)
# Thứ tự quan trọng — R2 phải chạy trước các rule dùng self.feat prefix
_RAW_RULES: list[tuple[str, str, str, str]] = [
    # R1: bare rolling_xxx() không có prefix self.feat → thêm prefix
    # Dùng callback để tránh double-prefix (xem _safe_prefix_sub)
    (r'\brolling_max\s*\(', "self.feat.rolling_max(", "R1a", "rolling_max → self.feat.rolling_max"),
    (r'\brolling_min\s*\(', "self.feat.rolling_min(", "R1b", "rolling_min → self.feat.rolling_min"),
    (r'\brolling_mean\s*\(', "self.feat.rolling_mean(", "R1c", "rolling_mean → self.feat.rolling_mean"),
    (r'\brolling_std\s*\(', "self.feat.rolling_std(", "R1d", "rolling_std → self.feat.rolling_std"),
    (r'\brolling_sum\s*\(', "self.feat.rolling_sum(", "R1e", "rolling_sum → self.feat.rolling_sum"),
    (r'\brolling_zscore\s*\(', "self.feat.rolling_zscore(", "R1f", "rolling_zscore → self.feat.rolling_zscore"),
    # R2: self.param_xxx → local variable xxx (LLM hay sinh ra sai pattern này)
    (r'\bself\.param_([a-zA-Z0-9_]+)\b', r'\1', "R2", "self.param_xxx → local variable xxx"),
    # R3: self.op.shift(self.op, x) → self.op.shift(x)
    (r'self\.op\.shift\s*\(\s*self\.op\s*,\s*', "self.op.shift(", "R3", "self.op.shift(self.op, x) → self.op.shift(x)"),
    # R4: Python boolean operators → Pandas bitwise
    (r'(?<![&|])\s*&&\s*(?![&|])', ' & ', "R4a", "&& → &"),
    (r'(?<![|])\s*\|\|\s*(?![|])', ' | ', "R4b", "|| → |"),
    # R5: numpy không available trong Sandbox → thay thế
    (r'\bnp\.abs\s*\(', "abs(", "R5a", "np.abs → abs"),
    (r'\bnp\.where\s*\(', "self.op.where(", "R5b", "np.where → self.op.where"),
    (r'\bnp\.sign\s*\(', "self.op.sign(", "R5c", "np.sign → self.op.sign"),
    (r'\bnp\.clip\s*\(', "self.op.clip(", "R5d", "np.clip → self.op.clip"),
    # R6: bare op functions không có prefix self.op
    (r'(?<!\.)(?<!self\.op\.)\bcrossed_above\s*\(', "self.op.crossed_above(", "R6a", "crossed_above → self.op.crossed_above"),
    (r'(?<!\.)(?<!self\.op\.)\bcrossed_below\s*\(', "self.op.crossed_below(", "R6b", "crossed_below → self.op.crossed_below"),
    # R7: pandas .rolling() chain calls vi phạm vectorized constraint
    # Không tự sửa được vì không biết chuyển thành feat nào → bỏ qua (R7 reserved)
    # R8: self.op.rolling_xxx / self.op.max/min → self.feat.rolling_xxx
    (r'\bself\.op\.rolling_(mean|max|min|std|sum|zscore)\b', r'self.feat.rolling_\1', "R8a", "self.op.rolling_xxx → self.feat.rolling_xxx"),
    (r'\bself\.op\.max\b', 'self.feat.rolling_max', "R8b", "self.op.max → self.feat.rolling_max"),
    (r'\bself\.op\.min\b', 'self.feat.rolling_min', "R8c", "self.op.min → self.feat.rolling_min"),
    # R9: roll_xxx / self.op.roll_xxx → self.feat.rolling_xxx
    (r'\bself\.feat\.roll_vwap\b', 'self.feat.rolling_vwap', "R9a", "self.feat.roll_vwap → self.feat.rolling_vwap"),
    (r'\bself\.feat\.roll_(mean|max|min|std|sum|zscore)\b', r'self.feat.rolling_\1', "R9b", "self.feat.roll_xxx → self.feat.rolling_xxx"),
    (r'\bself\.op\.roll_(mean|max|min|std|sum|zscore|vwap)\b', r'self.feat.rolling_\1', "R9c", "self.op.roll_xxx → self.feat.rolling_xxx"),
]


def _safe_prefix_sub(pattern: str, replacement: str, text: str) -> str:
    """
    Replace pattern with replacement only if not already prefixed by 'self.feat.' or 'self.op.'.

    Parameters
    ----------
    pattern : str
        The regex pattern to search for.
    replacement : str
        The replacement string.
    text : str
        The target text to search.

    Returns
    -------
    str
        The modified text.
    """
    compiled = re.compile(pattern)

    def replacer(m: re.Match) -> str:
        start = m.start()
        # Lấy 10 ký tự trước match để kiểm tra prefix
        prefix_slice = text[max(0, start - 10): start]
        if "self.feat." in prefix_slice or "self.op." in prefix_slice:
            return m.group()
        return replacement

    return compiled.sub(replacer, text)


def _apply_regex_rules(text: str, fix_log: list[str]) -> tuple[str, bool]:
    """
    Apply all deterministic regex rules to the text code.

    Parameters
    ----------
    text : str
        The code to modify.
    fix_log : list[str]
        Accumulator list for logging modifications.

    Returns
    -------
    tuple (str, bool)
        - modified_text : str (the updated code string)
        - was_changed : bool (True if changes were made)
    """
    original = text
    for pattern_str, replacement, rule_id, description in _RAW_RULES:
        # Các rule R1x cần safe prefix check
        if rule_id.startswith("R1") or rule_id.startswith("R6"):
            new_text = _safe_prefix_sub(pattern_str, replacement, text)
        else:
            new_text = re.sub(pattern_str, replacement, text)
        if new_text != text:
            fix_log.append(f"  [PRE-FIX {rule_id}] {description}")
            text = new_text
    return text, text != original


def _fix_unknown_feat_calls(code: str, fix_log: list[str]) -> tuple[str, bool]:
    """
    Detect calls to self.feat.XYZ not present in whitelisted features.
    
    Uses fuzzy matching to locate close matches and replace them.

    Parameters
    ----------
    code : str
        The code to inspect.
    fix_log : list[str]
        Accumulator list for logging changes.

    Returns
    -------
    tuple (str, bool)
        - modified_code : str
        - was_changed : bool
    """
    changed = False
    # Giữ reference tới code hiện tại để dùng trong closure
    current_code = code

    def replace_feat(match: re.Match) -> str:
        nonlocal changed, current_code
        func_name = match.group(1)
        if func_name.lower() in FEAT_WHITELIST:
            return match.group(0)
        candidates = get_close_matches(func_name.lower(), FEAT_WHITELIST, n=1, cutoff=0.75)
        if candidates:
            suggestion = candidates[0]
            fix_log.append(
                f"  [FUZZY] self.feat.{func_name} → self.feat.{suggestion}"
            )
            changed = True
            return f"self.feat.{suggestion}"
        # Không tìm được match → giữ nguyên, để LLM xử lý
        fix_log.append(
            f"  [UNKNOWN FEAT] self.feat.{func_name} — không có trong whitelist, không tìm được gợi ý"
        )
        return match.group(0)

    result = re.sub(r"self\.feat\.([a-zA-Z0-9_]+)", replace_feat, code)
    return result, changed


def _check_ast_syntax(code: str) -> tuple[bool, str]:
    """
    Check code syntax using Python's built-in AST parser.

    Parameters
    ----------
    code : str
        The code to parse.

    Returns
    -------
    tuple (bool, str)
        - is_valid : bool (True if compiles successfully)
        - error_message : str (syntax error traceback if invalid, else empty)
    """
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError dòng {e.lineno}: {e.msg} (text={e.text!r})"


def _fix_json_fields(idea: dict, fix_log: list[str]) -> tuple[dict, bool]:
    """
    Synchronize regex fixes back to the original JSON idea dictionary.

    Parameters
    ----------
    idea : dict
        The strategy idea dictionary containing formula definitions.
    fix_log : list[str]
        Accumulator list for logging modifications.

    Returns
    -------
    tuple (dict, bool)
        - updated_idea : dict
        - was_changed : bool
    """
    idea = copy.deepcopy(idea)
    changed = False
    formula = idea.get("formula", {})
    if not formula:
        return idea, False

    json_fix_log: list[str] = []

    # Fix entry/exit expression fields
    for field in ("entry_long", "entry_short", "exit_long", "exit_short"):
        val = formula.get(field)
        if isinstance(val, str):
            fixed, did_change = _apply_regex_rules(val, json_fix_log)
            if did_change:
                formula[field] = fixed
                changed = True

    # Fix indicator definition fields
    for indicator in formula.get("indicators", []):
        defn = indicator.get("definition")
        if isinstance(defn, str):
            fixed, did_change = _apply_regex_rules(defn, json_fix_log)
            if did_change:
                indicator["definition"] = fixed
                changed = True

    if changed:
        # Ghi log gộp, không in lại từng rule (đã in ở code phase)
        fix_log.append("  [JSON SYNC] Đã cập nhật JSON formula fields theo fixes trên")
        idea["formula"] = formula

    return idea, changed


# ── Public API ─────────────────────────────────────────────────────────────

def apply_prefixes(
    code: str,
    idea: dict,
) -> tuple[str, dict, bool, list[str]]:
    """
    Apply all deterministic syntax and prefix fixes on Python code and sync to JSON.

    Parameters
    ----------
    code : str
        The python source code generated from the JSON blueprint.
    idea : dict
        The original strategy idea dictionary.

    Returns
    -------
    tuple (str, dict, bool, list[str])
        - fixed_code : str
        - updated_idea : dict
        - was_modified : bool
        - fix_log : list[str]
    """
    fix_log: list[str] = []
    was_modified = False

    # Bước 1: Áp dụng regex rules lên code
    code, code_changed = _apply_regex_rules(code, fix_log)
    if code_changed:
        was_modified = True

    # Bước 2: Fuzzy match các self.feat.* không hợp lệ
    code, fuzzy_changed = _fix_unknown_feat_calls(code, fix_log)
    if fuzzy_changed:
        was_modified = True

    # Bước 3: Sync fixes ngược lại vào JSON fields
    updated_idea, json_changed = _fix_json_fields(idea, fix_log)
    if json_changed:
        was_modified = True
    else:
        updated_idea = copy.deepcopy(idea)

    # Bước 4: Kiểm tra AST syntax sau khi fix
    is_valid, syntax_error = _check_ast_syntax(code)
    if not is_valid:
        fix_log.append(f"  [AST] Syntax vẫn lỗi sau pre-fix: {syntax_error}")

    return code, updated_idea, was_modified, fix_log


def check_tautology(code: str) -> list[str]:
    """
    Detect logical conditions that are tautological (always True or always False).

    Checks for patterns like `x == x` or `x != x` which usually represent logic bugs.

    Parameters
    ----------
    code : str
        The strategy source code.

    Returns
    -------
    list[str]
        A list of warnings describing the detected tautologies.
    """
    warnings: list[str] = []
    # Dạng `a != a` — always False (trừ NaN)
    for m in re.finditer(r'\b(\w+)\s*!=\s*\1\b', code):
        warnings.append(
            f"  [TAUTOLOGY] `{m.group()}` → luôn False (chỉ True với NaN). "
            f"Entry/Exit sẽ hiếm khi trigger — Tầng 4, cần LLM sửa logic."
        )
    # Dạng `a == a` — always True
    for m in re.finditer(r'\b(\w+)\s*==\s*\1\b', code):
        warnings.append(
            f"  [TAUTOLOGY] `{m.group()}` → luôn True. "
            f"Condition vô nghĩa — Tầng 4, cần LLM sửa logic."
        )
    return warnings
