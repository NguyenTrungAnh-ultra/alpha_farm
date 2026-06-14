import os
import sys
import json
import re
import traceback
import pandas as pd
import ast

from pathlib import Path

# Add project root to path
PROJECT_ROOT = "f:/Projects/alpha_farm"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from xno_sdk.emulator import XNOPlatformEmulator
from backtest.engine import load_data

class XNOASTFixer(ast.NodeTransformer):
    def __init__(self):
        # Known functions that return tuples
        self.tuple_funcs = {'macd', 'macdfix', 'macdext', 'stoch', 'stochf', 'stochrsi', 'bbands', 'minmax', 'minmaxindex', 'aroon', 'mama', 'sine'}

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        # Convert And() -> BitAnd(), Or() -> BitOr()
        if isinstance(node.op, ast.And):
            op = ast.BitAnd()
        elif isinstance(node.op, ast.Or):
            op = ast.BitOr()
        else:
            return node
            
        # Build BinOp tree
        expr = node.values[0]
        for val in node.values[1:]:
            expr = ast.BinOp(left=expr, op=op, right=val)
        return expr

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in ['clip', 'shift', 'fillna', 'ffill']:
                # Transform `foo.clip(a, b)` -> `self.op.clip(foo, a, b)`
                new_func = ast.Attribute(
                    value=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr='op', ctx=ast.Load()),
                    attr=attr_name, ctx=ast.Load()
                )
                node.args.insert(0, node.func.value)
                node.func = new_func
            elif attr_name in ['mean', 'max', 'min', 'std', 'sum']:
                val = node.func.value
                if isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute) and val.func.attr == 'rolling':
                    obj = val.func.value
                    window_kw = None
                    for kw in val.keywords:
                        if kw.arg == 'window':
                            window_kw = kw
                    
                    target_func = f"rolling_{attr_name}"
                    new_func = ast.Attribute(
                        value=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr='feat', ctx=ast.Load()),
                        attr=target_func, ctx=ast.Load()
                    )
                    
                    new_args = [obj]
                    new_keywords = []
                    if window_kw:
                        new_keywords.append(window_kw)
                    return ast.Call(func=new_func, args=new_args, keywords=new_keywords)
        return node
        
    def visit_Attribute(self, node):
        self.generic_visit(node)
        # Convert `foo.upperband` -> `foo[0]`
        if node.attr in ['upperband', 'fastk', 'macd']:
            return ast.Subscript(value=node.value, slice=ast.Constant(value=0), ctx=ast.Load())
        if node.attr in ['middleband', 'fastd', 'macdsignal']:
            return ast.Subscript(value=node.value, slice=ast.Constant(value=1), ctx=ast.Load())
        if node.attr in ['lowerband', 'macdhist']:
            return ast.Subscript(value=node.value, slice=ast.Constant(value=2), ctx=ast.Load())
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if isinstance(node.left, ast.Call) and isinstance(node.left.func, ast.Attribute) and node.left.func.attr in self.tuple_funcs:
            node.left = ast.Subscript(value=node.left, slice=ast.Constant(value=0), ctx=ast.Load())
        
        for i, comp in enumerate(node.comparators):
            if isinstance(comp, ast.Call) and isinstance(comp.func, ast.Attribute) and comp.func.attr in self.tuple_funcs:
                node.comparators[i] = ast.Subscript(value=comp, slice=ast.Constant(value=0), ctx=ast.Load())
        return node
        
    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.left, ast.Call) and isinstance(node.left.func, ast.Attribute) and node.left.func.attr in self.tuple_funcs:
            node.left = ast.Subscript(value=node.left, slice=ast.Constant(value=0), ctx=ast.Load())
        if isinstance(node.right, ast.Call) and isinstance(node.right.func, ast.Attribute) and node.right.func.attr in self.tuple_funcs:
            node.right = ast.Subscript(value=node.right, slice=ast.Constant(value=0), ctx=ast.Load())
        return node

    def visit_Assign(self, node):
        self.generic_visit(node)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr in self.tuple_funcs:
                node.value = ast.Subscript(value=node.value, slice=ast.Constant(value=0), ctx=ast.Load())
        return node


CDL_PATTERN_MAPPING = {
    "cdl_piercing": "piercing_pattern",
    "cdlpiercing": "piercing_pattern",
    "cdl_engulfing": "engulfing_pattern",
    "cdlengulfing": "engulfing_pattern",
    "cdl_harami": "harami_pattern",
    "cdlharami": "harami_pattern",
    "cdl_haramicross": "harami_cross_pattern",
    "cdlharamicross": "harami_cross_pattern",
    "cdl_hikkake": "hikkake_pattern",
    "cdlhikkake": "hikkake_pattern",
    "cdl_inneck": "in_neck_pattern",
    "cdlinneck": "in_neck_pattern",
    "cdl_onneck": "on_neck_pattern",
    "cdlonneck": "on_neck_pattern",
    
    # Spelled-out/numeric mappings
    "cdl3whitesoldiers": "three_white_soldiers",
    "3whitesoldiers": "three_white_soldiers",
    "cdl3blackcrows": "three_black_crows",
    "3blackcrows": "three_black_crows",
    "cdl2crows": "two_crows",
    "2crows": "two_crows",
    "cdl3inside": "three_inside_up_down",
    "3inside": "three_inside_up_down",
    "cdl3outside": "three_outside_up_down",
    "3outside": "three_outside_up_down",
    "cdl3linestrike": "three_line_strike",
    "3linestrike": "three_line_strike",
    "cdl3starsinsouth": "three_stars_in_south",
    "3starsinsouth": "three_stars_in_south",
}

def map_cdl_patterns(expr: str) -> str:
    if not expr:
        return ""
    
    def replace_func(match):
        full_match = match.group(0)
        key = full_match.lower()
        key_no_underscore = key.replace("_", "")
        
        if key in CDL_PATTERN_MAPPING:
            return CDL_PATTERN_MAPPING[key]
        elif key_no_underscore in CDL_PATTERN_MAPPING:
            return CDL_PATTERN_MAPPING[key_no_underscore]
            
        # Fallback: remove cdl_ or cdl prefix and ensure valid Python identifier
        clean_key = key.replace("cdl_", "").replace("cdl", "")
        if clean_key and clean_key[0].isdigit():
            digit_map = {"2": "two_", "3": "three_", "4": "four_", "5": "five_"}
            first_digit = clean_key[0]
            prefix_str = digit_map.get(first_digit, "num_")
            clean_key = prefix_str + clean_key[1:]
            
        if not clean_key.endswith("_pattern") and clean_key not in ["three_white_soldiers", "three_black_crows", "two_crows", "three_inside_up_down", "three_outside_up_down", "three_line_strike", "three_stars_in_south"]:
            clean_key = f"{clean_key}_pattern"
        return clean_key
        
    return re.sub(r'\b(cdl_?[a-zA-Z0-9_]+|[2-5][a-zA-Z_][a-zA-Z0-9_]*)\b', replace_func, expr, flags=re.IGNORECASE)

def inject_engine_prefixes(expr: str) -> str:
    if not expr:
        return ""
    
    # Auto-inject self.feat. for known functions if missing
    feat_pattern = r'(?<!\.)(?<!self\.feat\.)\b(sma|ema|dema|tema|wma|kama|t3|trima|midpoint|midprice|sar|linearreg|linearreg_slope|rsi|stoch|stochf|stochrsi|macd|mom|roc|rocp|willr|cci|cmo|mfi|ultosc|trix|adx|adxr|aroon|aroonosc|dx|minus_di|plus_di|apo|ppo|bop|atr|natr|trange|bbands|ad|adosc|obv|max|min|stddev|var|linearreg_angle|piercing_pattern|engulfing_pattern|harami_pattern|harami_cross_pattern|hikkake_pattern|modified_hikkake_pattern|in_neck_pattern|on_neck_pattern|three_white_soldiers|three_black_crows|two_crows|three_inside_up_down|three_outside_up_down|three_line_strike|three_stars_in_south|identical_three_crows|upside_gap_two_crows|cdl[a-z0-9_]+)\s*\('
    expr = re.sub(feat_pattern, r'self.feat.\1(', expr, flags=re.IGNORECASE)
    # Lowercase the function name after self.feat.
    expr = re.sub(r'self\.feat\.([A-Za-z0-9_]+)', lambda m: f"self.feat.{m.group(1).lower()}", expr)
    
    # Auto-inject self.op. for known operator functions if missing
    op_pattern = r'(?<!\.)(?<!self\.op\.)\b(crossed|crossed_above|crossed_below|current|previous|shift|diff|pct_change|rising|falling|fillna|ffill|abs|clip|isna|notna|isfinite|zero_ifna|sign|replace|between|where|value_when|bars_since|hold_for|crossed_above_value|crossed_below_value)\s*\('
    expr = re.sub(op_pattern, r'self.op.\1(', expr, flags=re.IGNORECASE)
    
    return expr

def wrap_comparison_clauses(expr: str) -> str:
    if not expr:
        return ""
    
    # Split by AND / OR / & / | operators (case-insensitively)
    parts = re.split(r'(\s+and\s+|\s+or\s+|\s+&&\s+|\s+\|\|\s+|\s*&\s*|\s*\|\s*)', expr, flags=re.IGNORECASE)
    
    new_parts = []
    for part in parts:
        part_lower = part.lower().strip()
        if not part_lower:
            new_parts.append(part)
            continue
            
        # Map to the Python pandas equivalent logical operators
        if part_lower in ['and', '&&', '&']:
            new_parts.append(' & ')
        elif part_lower in ['or', '||', '|']:
            new_parts.append(' | ')
        else:
            clause = part.strip()
            # Wrap comparison in parentheses if it's not already wrapped
            has_comparison = any(op in clause for op in ['>', '<', '==', '!=', '>=', '<='])
            is_wrapped = clause.startswith('(') and clause.endswith(')')
            if has_comparison and not is_wrapped:
                clause = f"({clause})"
            new_parts.append(clause)
            
    return "".join(new_parts)

def clean_expression(expr: str) -> str:
    """Clean logical operators in entry/exit expression for Python."""
    if not expr:
        return ""
    # Map TA-Lib CDL function naming to whitelisted XNO patterns
    expr = map_cdl_patterns(expr)
    # Auto-inject self.feat. and self.op. prefixes
    expr = inject_engine_prefixes(expr)
    # Wrap comparison clauses in parentheses to fix precedence
    expr = wrap_comparison_clauses(expr)
    # Replace forbidden open variable name with open_price
    expr = re.sub(r'\bopen\b', 'open_price', expr)
    # Strip trailing period if any
    expr = expr.strip().rstrip('.')
    
    # Fix tuple attribute access
    expr = expr.replace('.upperband', '[0]')
    expr = expr.replace('.middleband', '[1]')
    expr = expr.replace('.lowerband', '[2]')
    expr = expr.replace('.fastk', '[0]')
    expr = expr.replace('.fastd', '[1]')
    
    # Balance parentheses roughly
    open_p = expr.count('(')
    close_p = expr.count(')')
    if open_p > close_p:
        expr += ')' * (open_p - close_p)
        
    return expr





def generate_python_code(idea: dict) -> str:
    name = idea.get('name', 'CustomStrategy')
    formula = idea.get('formula', {})
    param_space = idea.get('param_space', {})
    
    lines = []
    lines.append("from xno_sdk.engine import SimpleAlgorithm")
    lines.append("")
    lines.append("class CustomStrategy(SimpleAlgorithm):")
    lines.append("    def __algorithm__(self):")
    lines.append("        # 1. Parameter declarations")
    
    # Generate parameters
    for param_name, param_info in param_space.items():
        p_type = param_info.get('type', 'int')
        low = param_info.get('low')
        high = param_info.get('high')
        
        # Determine default value as midpoint
        if p_type == 'int':
            default_val = int((low + high) // 2)
            lines.append(f"        self.{param_name} = int(self.{param_name} if '{param_name}' in self.__dict__ else {default_val})")
        else:
            default_val = float((low + high) / 2.0)
            # Round float default to a clean representation
            default_val = round(default_val, 4)
            lines.append(f"        self.{param_name} = float(self.{param_name} if '{param_name}' in self.__dict__ else {default_val})")
            
    lines.append("")
    lines.append("        # 2. Local variables for parameters")
    for param_name in param_space.keys():
        lines.append(f"        {param_name} = self.{param_name}")
        
    lines.append("")
    lines.append("        # 3. Inputs")
    lines.append("        open_price = self.data.pv_open")
    lines.append("        high = self.data.pv_high")
    lines.append("        low = self.data.pv_low")
    lines.append("        close = self.data.pv_close")
    lines.append("        volume = self.data.pv_volume")
    lines.append("")
    
    lines.append("        # 4. Indicators")
    indicators = formula.get('indicators', [])
    for ind in indicators:
        ind_name = ind.get('name')
        ind_def = ind.get('definition')
        
        # Apply pattern mapping
        ind_def = map_cdl_patterns(ind_def)
        # Auto-inject self.feat. and self.op. prefixes
        ind_def = inject_engine_prefixes(ind_def)
        # Replace forbidden open variable name with open_price
        ind_def = re.sub(r'\bopen\b', 'open_price', ind_def)
        # Clean trailing comments or -> returns
        ind_def = re.sub(r'\s*(->|#).*$', '', ind_def)
        # Clean trailing positional args
        ind_def = re.sub(r',\s*\d+\s*\)', ')', ind_def)
        # Fix tuple attribute access
        ind_def = ind_def.replace('.upperband', '[0]').replace('.middleband', '[1]').replace('.lowerband', '[2]')
        ind_def = ind_def.replace('.fastk', '[0]').replace('.fastd', '[1]')
        
        # Apply anti-singularity adjustments if dividing by volume or high-low range
        # Check if the definition contains division by volume or price range
        # Note: self.data.pv_volume has volume = 0, so division by volume is very dangerous
        if '/' in ind_def:
            # Check for close/volume or similar
            if 'volume' in ind_def and not '1e-8' in ind_def and not 'isfinite' in ind_def:
                # Add tiny constant to volume or wrap
                # E.g., change / volume to / (volume + 1e-8)
                # But let's be careful and use re.sub or a replacement
                ind_def = re.sub(r'/\s*volume\b', '/ (volume + 1e-8)', ind_def)
            if ('high - low' in ind_def or 'high-low' in ind_def) and not '1e-8' in ind_def and not 'isfinite' in ind_def:
                ind_def = ind_def.replace('high - low', '(high - low + 1e-8)')
                ind_def = ind_def.replace('high-low', '(high - low + 1e-8)')
                
        lines.append(f"        {ind_name} = {ind_def}")
        
    lines.append("")
    lines.append("        # 5. Entry logic")
    entry_long = clean_expression(formula.get('entry_long', ''))
    entry_short = clean_expression(formula.get('entry_short', ''))
    
    lines.append(f"        long_setup = {entry_long}")
    lines.append(f"        short_setup = {entry_short}")
    lines.append("")
    
    lines.append("        # 6. Exit logic")
    exit_long = clean_expression(formula.get('exit_long', ''))
    exit_short = clean_expression(formula.get('exit_short', ''))
    
    if not exit_long: exit_long = "False"
    if not exit_short: exit_short = "False"
    
    lines.append(f"        exit_long = {exit_long}")
    lines.append(f"        exit_short = {exit_short}")
    lines.append("        exit_setup = exit_long | exit_short")
    lines.append("")
    
    lines.append("        # 7. Set positions (EXIT first, ENTRY second)")
    lines.append("        self.set_positions(exit_setup, position=0.0)")
    lines.append("        self.set_positions(long_setup, position=1.0)")
    lines.append("        self.set_positions(short_setup, position=-1.0)")
    lines.append("")
    
    code = "\n".join(lines)
    
    try:
        tree = ast.parse(code)
        fixer = XNOASTFixer()
        tree = fixer.visit(tree)
        ast.fix_missing_locations(tree)
        code = ast.unparse(tree)
    except SyntaxError as e:
        print(f"  AST Fixer skipped due to SyntaxError: {e}")
        
    return code

def main():
    ideas_dir = os.path.join(PROJECT_ROOT, "agent", "results", "ideas")
    output_dir = os.path.join(PROJECT_ROOT, "agent", "results")
    
    if not os.path.exists(ideas_dir):
        print(f"Error: ideas directory not found at {ideas_dir}")
        sys.exit(1)
        
    json_files = [f for f in os.listdir(ideas_dir) if f.endswith('.json')]
    print(f"Found {len(json_files)} strategy ideas to convert.")
    
    # Pre-load data for each timeframe to speed up validation
    data_cache = {}
    
    success_count = 0
    fail_count = 0
    
    emulator = XNOPlatformEmulator(verbose=False)
    
    for filename in json_files:
        filepath = os.path.join(ideas_dir, filename)
        py_filename = filename.replace('.json', '.py')
        py_filepath = os.path.join(output_dir, py_filename)
        pushed_filepath = os.path.join(output_dir, "pushed", py_filename)
        failed_filepath = os.path.join(output_dir, "failed_conversions", py_filename)
        
        if os.path.exists(py_filepath) or os.path.exists(pushed_filepath) or os.path.exists(failed_filepath):
            print(f"Skipping {filename} - already converted.")
            continue
        
        print(f"\nProcessing {filename}...")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                idea = json.load(f)
                
            code = generate_python_code(idea)
            
            # Get timeframe for validation
            tf = idea.get('timeframe', '10m')
            if tf not in data_cache:
                print(f"  Loading {tf} data for validation...")
                data_cache[tf] = load_data(tf)
            
            # Validate
            print("  Validating generated code in XNO Sandbox...")
            
            # Lưu code ra file tạm để emulator đọc
            with open(py_filepath, 'w', encoding='utf-8') as f:
                f.write(code)
                
            try:
                # Emulator tự handle sandbox validation
                metrics = emulator.get_metrics(py_filepath, tf)
                
                sharpe = metrics.get('sharpe_ratio', 0.0)
                cagr = metrics.get('cagr', 0.0)
                
                if sharpe > 1.3 and cagr > 0.15:
                    print(f"  ✅ Code generated and validated successfully! Saved to {py_filename}")
                    print(f"     > Initial Sharpe: {sharpe:.4f} | CAGR: {cagr*100:.1f}%")
                    success_count += 1
                else:
                    print(f"  ❌ Validation failed: Performance criteria not met (Sharpe={sharpe:.4f}, CAGR={cagr*100:.1f}%)")
                    if os.path.exists(py_filepath):
                        os.remove(py_filepath)
                    print(f"  Deleted failing strategy file: {py_filename}")
                    fail_count += 1
                    
            except Exception as e:
                error = str(e)
                print(f"  ❌ Validation error: {error}")
                # Đưa file bị lỗi vào failed_conversions và xóa khỏi kết quả
                fail_filepath = os.path.join(output_dir, "failed_conversions", py_filename)
                os.makedirs(os.path.dirname(fail_filepath), exist_ok=True)
                if os.path.exists(py_filepath):
                    os.replace(py_filepath, fail_filepath)
                print(f"  Saved failed attempt to failed_conversions/{py_filename}")
                fail_count += 1
                
        except Exception as e:
            print(f"  💥 Exception occurred during processing: {e}")
            traceback.print_exc()
            fail_count += 1
            
    print("\n" + "="*50)
    print(f"Conversion complete!")
    print(f"Successful conversions: {success_count}")
    print(f"Failed conversions: {fail_count}")
    print("="*50)

if __name__ == "__main__":
    main()
