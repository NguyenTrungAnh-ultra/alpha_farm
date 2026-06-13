import os
import sys
import json
import re
import traceback
import pandas as pd
from pathlib import Path

# Add project root to path
PROJECT_ROOT = "f:/Projects/alpha_farm"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from xno_sdk.emulator import XNOPlatformEmulator
from backtest.engine import load_data

def clean_expression(expr: str) -> str:
    """Clean logical operators in entry/exit expression for Python."""
    if not expr:
        return ""
    # Correct TA-Lib CDL function naming (e.g. cdl_engulfing -> cdlengulfing)
    expr = re.sub(r'\bcdl_(\w+)\b', lambda m: f"cdl{m.group(1)}", expr, flags=re.IGNORECASE)
    # Replace forbidden open variable name with open_price
    expr = re.sub(r'\bopen\b', 'open_price', expr)
    # Replace case-insensitive ' or ' and ' and ' with '|' and '&'
    expr = re.sub(r'\bor\b', '|', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\band\b', '&', expr, flags=re.IGNORECASE)
    # Strip trailing period if any
    expr = expr.strip().rstrip('.')
    return expr

def parse_exit_logic(exit_logic_str: str) -> tuple[str, str]:
    """Parse exit_logic string into exit_long and exit_short expressions."""
    parts = re.split(r'[;\.]', exit_logic_str)
    exit_long = ""
    exit_short = ""
    for part in parts:
        part = part.strip()
        if not part: continue
        if 'long' in part.lower():
            expr = re.sub(r'.*long.*?(:|when)\s*', '', part, flags=re.IGNORECASE).strip()
            expr = re.sub(r'^(?:exit\s+when|exit)\s*', '', expr, flags=re.IGNORECASE).strip()
            exit_long = clean_expression(expr)
        elif 'short' in part.lower():
            expr = re.sub(r'.*short.*?(:|when)\s*', '', part, flags=re.IGNORECASE).strip()
            expr = re.sub(r'^(?:exit\s+when|exit)\s*', '', expr, flags=re.IGNORECASE).strip()
            exit_short = clean_expression(expr)
            
    return exit_long, exit_short

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
            lines.append(f"        self.{param_name} = {default_val}")
        else:
            default_val = float((low + high) / 2.0)
            # Round float default to a clean representation
            default_val = round(default_val, 4)
            lines.append(f"        self.{param_name} = {default_val}")
            
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
        
        # Correct TA-Lib CDL function naming (e.g. cdl_engulfing -> cdlengulfing)
        ind_def = re.sub(r'\bcdl_(\w+)\b', lambda m: f"cdl{m.group(1)}", ind_def, flags=re.IGNORECASE)
        # Replace forbidden open variable name with open_price
        ind_def = re.sub(r'\bopen\b', 'open_price', ind_def)
        
        # Auto-inject self.feat. for known functions if missing
        func_pattern = r'(?<!self\.feat\.)\b(sma|ema|dema|tema|wma|kama|t3|trima|midpoint|midprice|sar|linearreg|linearreg_slope|rsi|stoch|stochf|stochrsi|macd|mom|roc|rocp|willr|cci|cmo|mfi|ultosc|trix|adx|adxr|aroon|aroonosc|dx|minus_di|plus_di|apo|ppo|bop|atr|natr|trange|bbands|ad|adosc|obv|max|min|stddev|var|linearreg_angle|cdl[a-z0-9_]+)\s*\('
        ind_def = re.sub(func_pattern, r'self.feat.\1(', ind_def, flags=re.IGNORECASE)
        # Lowercase the function name after self.feat.
        ind_def = re.sub(r'self\.feat\.([A-Za-z0-9_]+)', lambda m: f"self.feat.{m.group(1).lower()}", ind_def)
        
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
    exit_logic_str = formula.get('exit_logic', '')
    exit_long, exit_short = parse_exit_logic(exit_logic_str)
    
    lines.append(f"        exit_long = {exit_long}")
    lines.append(f"        exit_short = {exit_short}")
    lines.append("        exit_setup = exit_long | exit_short")
    lines.append("")
    
    lines.append("        # 7. Set positions (EXIT first, ENTRY second)")
    lines.append("        self.set_positions(exit_setup, position=0.0)")
    lines.append("        self.set_positions(long_setup, position=1.0)")
    lines.append("        self.set_positions(short_setup, position=-1.0)")
    lines.append("")
    
    return "\n".join(lines)

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
                print(f"  ✅ Code generated and validated successfully! Saved to {py_filename}")
                print(f"     > Initial Sharpe: {metrics.get('sharpe_ratio', 0.0):.4f}")
                success_count += 1
            except Exception as e:
                error = str(e)
                print(f"  ❌ Validation failed: {error}")
                # Đưa file bị lỗi vào failed_conversions và xóa khỏi kết quả
                fail_filepath = os.path.join(output_dir, "failed_conversions", py_filename)
                os.makedirs(os.path.dirname(fail_filepath), exist_ok=True)
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
