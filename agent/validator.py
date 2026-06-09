"""
Strategy Code Validator (XNO Engine)
=====================================
Validates LLM-generated strategy code for the XNOQuant-style engine.

Validation steps:
    1. Syntax check (compile)
    2. Import + exec in sandbox
    3. Find strategy class (inherits SimpleAlgorithm)
    4. Instantiate with default params
    5. Run run_algorithm() on sample data — must return pd.Series of positions
"""

import sys
import traceback
from typing import Optional, Type, Tuple

import numpy as np
import pandas as pd


def extract_code(text: str) -> str:
    """Extract Python code from LLM response (may contain ```python blocks)."""
    import re
    
    # Try to find ```python ... ``` block
    pattern = r'```python\s*\n([\s\S]*?)\n```'
    matches = re.findall(pattern, text)
    if matches:
        return matches[0].strip()
    
    # Try generic ``` block
    pattern = r'```\s*\n([\s\S]*?)\n```'
    matches = re.findall(pattern, text)
    if matches:
        return matches[0].strip()
    
    # Return as-is (might be raw code)
    return text.strip()


def validate_strategy(
    code: str,
    sample_data: pd.DataFrame,
    verbose: bool = False,
) -> Tuple[Optional[Type], Optional[str]]:
    """
    Validate strategy code and return the strategy class if valid.
    
    Parameters
    ----------
    code : str
        Python source code of the strategy.
    sample_data : pd.DataFrame
        Sample data for testing (OHLCV with Datetime index).
    verbose : bool
        Print debug info.
    
    Returns
    -------
    (strategy_class, error_message)
        strategy_class is None if validation failed.
        error_message describes what went wrong.
    """
    
    # ── Step 1: Syntax check ──
    try:
        compile(code, '<strategy>', 'exec')
        if verbose:
            print("  ✅ Syntax OK")
    except SyntaxError as e:
        return None, f"SyntaxError: {e}"
    
    # ── Step 2: Execute in sandbox ──
    sandbox = {}
    try:
        exec(code, sandbox)
        if verbose:
            print("  ✅ Exec OK")
    except Exception as e:
        return None, f"ExecError: {type(e).__name__}: {e}"
    
    # ── Step 3: Find strategy class (inherits SimpleAlgorithm) ──
    from backtest.strategy import SimpleAlgorithm
    
    strategy_class = None
    for name, obj in sandbox.items():
        if (isinstance(obj, type) and 
            issubclass(obj, SimpleAlgorithm) and 
            obj is not SimpleAlgorithm):
            strategy_class = obj
            break
    
    if strategy_class is None:
        return None, "No class inheriting SimpleAlgorithm found in code"
    
    if verbose:
        print(f"  ✅ Found class: {strategy_class.__name__}")
    
    # ── Step 4: Instantiate ──
    try:
        strategy = strategy_class()
        if verbose:
            print(f"  ✅ Instantiated with params: {strategy.params}")
    except Exception as e:
        return None, f"InstantiationError: {type(e).__name__}: {e}"
    
    # Check params dict exists
    if not hasattr(strategy, 'params') or not isinstance(strategy.params, dict):
        return None, "Strategy missing 'params' dict attribute"
    
    # ── Step 5: Run run_algorithm() on sample data ──
    try:
        # Use a subset for speed
        test_data = sample_data.head(500).copy()
        positions = strategy.run_algorithm(test_data)
        
        if not isinstance(positions, pd.Series):
            return None, f"run_algorithm() returned {type(positions)}, expected pd.Series"
        
        if len(positions) != len(test_data):
            return None, (f"run_algorithm() returned {len(positions)} positions "
                         f"but data has {len(test_data)} bars")
        
        # Check positions are valid numeric values
        if positions.isna().all():
            return None, "All positions are NaN — indicators likely need more warmup data"
        
        # Check we have at least some non-zero positions
        unique_pos = positions.dropna().unique()
        if verbose:
            print(f"  ✅ run_algorithm() OK (unique positions: {sorted(unique_pos)})")
        
    except Exception as e:
        tb = traceback.format_exc()
        return None, f"run_algorithm() failed: {type(e).__name__}: {e}\n{tb[-500:]}"
    
    return strategy_class, None
