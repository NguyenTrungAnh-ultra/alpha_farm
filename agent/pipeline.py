"""
Strategy Generation Pipeline (XNO Engine)
============================================
Main orchestrator that generates, validates, optimizes, and evaluates
trading strategies across all timeframes using LLM.

Usage (in notebook):
    from agent.pipeline import run_pipeline, load_cookies
    
    portfolio, stats = run_pipeline(
        cookies=load_cookies(),
        n_strategies=50,
        model="pro",
    )
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# Add project root to path
PROJECT_ROOT = str(Path(__file__).parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backtest.engine import XNOBacktestEngine, load_data
from backtest import reporting
from backtest.optimizer import Optimizer, IntParam, FloatParam, CategoricalParam

from agent.gemini_client import GeminiChat, extract_json
from agent.prompts import build_idea_prompt, build_code_prompt, build_fix_prompt
from agent.validator import validate_strategy, extract_code
from agent.portfolio import PortfolioManager


def load_cookies(filepath: str = None) -> str:
    """Read cookie string from cookies.txt (first non-comment line)."""
    if filepath is None:
        filepath = os.path.join(PROJECT_ROOT, "cookies.txt")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                return line
    raise ValueError(f"No cookies found in {filepath}")


# ─── Timeframe Configuration ────────────────────────────────────────
TIMEFRAME_ORDER = ["5m", "10m", "15m", "30m", "1m"]  # 1m last (slowest)


# ─── Helpers ─────────────────────────────────────────────────────────

def _parse_param_space(param_space_dict: dict) -> dict:
    """Convert JSON param_space to Optimizer param objects."""
    result = {}
    for name, spec in param_space_dict.items():
        ptype = spec.get('type', 'int')
        low = spec.get('low', 1)
        high = spec.get('high', 100)
        step = spec.get('step', 1 if ptype == 'int' else None)
        
        if ptype == 'int':
            result[name] = IntParam(int(low), int(high), step=int(step) if step else 1)
        elif ptype == 'float':
            result[name] = FloatParam(float(low), float(high), step=float(step) if step else None)
        elif ptype == 'categorical':
            result[name] = CategoricalParam(spec.get('choices', []))
    return result


def _log_entry(log_path: Path, entry: dict):
    """Append a log entry to the JSONL log file."""
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')


# ─── Main Pipeline ──────────────────────────────────────────────────

def run_pipeline(
    cookies,  # str or dict
    n_strategies: int = 50,
    model: str = "pro",
    n_trials: int = 100,
    request_delay: float = 5.0,
    results_dir: str = "agent/results",
    # Engine params
    initial_capital: float = None,
    margin_rate: float = None,
    fee_per_contract: float = None,
    # Optimization
    objective: str = 'sharpe_ratio',
    direction: str = 'maximize',
    # Portfolio criteria overrides
    max_correlation: float = None,
    verbose: bool = True,
):
    """
    Run the full strategy generation pipeline.
    
    Parameters
    ----------
    cookies : str or dict
        Google cookies for GeminiChat.
    n_strategies : int
        Total rounds to attempt.
    model : str
        Gemini model to use ("pro", "flash", etc.)
    n_trials : int
        Optuna trials per strategy optimization.
    request_delay : float
        Seconds between LLM requests.
    results_dir : str
        Directory to save results.
    initial_capital : float, optional
        Override vốn ban đầu (default: 1 tỷ VND from constants).
    margin_rate : float, optional
        Override tỷ lệ ký quỹ (default: 28.5%).
    fee_per_contract : float, optional
        Override phí mỗi HĐ/chiều (default: 6,000 VND).
    objective : str
        Metric to optimize. Options: 'sharpe_ratio', 'calmar_ratio', 
        'profit_factor', 'total_pnl', 'cagr', 'win_rate', 'max_drawdown_pct'.
    direction : str
        'maximize' or 'minimize'.
    max_correlation : float, optional
        Override max correlation threshold (default: 0.5).
    verbose : bool
        Print detailed progress.
    """
    
    # Build engine config (only include overrides)
    engine_config = {}
    if initial_capital is not None:
        engine_config['initial_capital'] = initial_capital
    if margin_rate is not None:
        engine_config['margin_rate'] = margin_rate
    if fee_per_contract is not None:
        engine_config['fee_per_contract'] = fee_per_contract
    
    # Display config
    from backtest.constants import INITIAL_CAPITAL, MARGIN_RATE, FEE_PER_CONTRACT_PER_SIDE
    disp_capital = engine_config.get('initial_capital', INITIAL_CAPITAL)
    disp_margin = engine_config.get('margin_rate', MARGIN_RATE)
    disp_fee = engine_config.get('fee_per_contract', FEE_PER_CONTRACT_PER_SIDE)
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           AUTO STRATEGY GENERATION PIPELINE                ║
║  Target: {n_strategies} strategies | Model: {model:15s}          ║
║  Timeframes: {', '.join(TIMEFRAME_ORDER):40s}  ║
║  Optimization: {n_trials} trials/strategy (Bayesian)           ║
║  Objective: {objective:20s} ({direction})             ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # ── Initialize ──
    chat = GeminiChat(
        cookies=cookies,
        model=model,
        request_delay=request_delay,
        max_retries=5,
        timeout=120,
        verbose=True,
    )
    print(f"[Pipeline] GeminiChat ready: {chat}")
    
    portfolio = PortfolioManager(results_dir=results_dir, max_correlation=max_correlation)
    print(f"[Pipeline] Portfolio: {len(portfolio.strategies)} existing strategies")
    print(f"[Pipeline] Engine: capital={disp_capital:,.0f} | margin={disp_margin:.1%} | "
          f"fee={disp_fee:,.0f}/HĐ/chiều")
    
    # Pre-load all data
    print("[Pipeline] Loading data...")
    all_data = {}
    for tf in TIMEFRAME_ORDER:
        try:
            df = load_data(tf)
            all_data[tf] = df
            print(f"  {tf:>4s}: {len(df):>8,} bars ({df.index[0].date()} → {df.index[-1].date()})")
        except Exception as e:
            print(f"  {tf:>4s}: FAILED ({e})")
    
    # Log file
    log_path = Path(results_dir) / "pipeline_log.jsonl"
    
    # Load ALL previously tried strategy names (accepted + rejected)
    tried_strategies = set()
    if log_path.exists():
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    name = entry.get('name', '')
                    if name:
                        tried_strategies.add(name)
                except json.JSONDecodeError:
                    continue
        print(f"[Pipeline] Loaded {len(tried_strategies)} previously tried strategies")
    
    # ── Stats ──
    stats = {
        'total_attempts': 0,
        'idea_generated': 0,
        'code_generated': 0,
        'validation_passed': 0,
        'optimization_done': 0,
        'accepted': 0,
        'rejected_criteria': 0,
        'rejected_correlation': 0,
        'errors': 0,
    }
    start_time = time.time()
    
    consecutive_errors = 0  # Track consecutive failures for session recovery
    
    # ── Main Loop ──
    for round_num in range(1, n_strategies + 1):
        # Pick timeframe (cycle through)
        tf_idx = (round_num - 1) % len(TIMEFRAME_ORDER)
        tf = TIMEFRAME_ORDER[tf_idx]
        
        if tf not in all_data:
            print(f"\n[Round {round_num}] ⏭️  Skip {tf} (no data)")
            continue
        
        data = all_data[tf]
        stats['total_attempts'] += 1
        
        elapsed = time.time() - start_time
        rate = stats['accepted'] / max(stats['total_attempts'], 1)
        
        print(f"\n{'─'*60}")
        print(f"  Round {round_num}/{n_strategies} | TF={tf} | "
              f"Accepted: {stats['accepted']} | "
              f"Rate: {rate:.0%} | "
              f"Elapsed: {elapsed/60:.0f}m")
        print(f"{'─'*60}")
        
        try:
            # ═══ STEP 1: Generate Strategy Idea ═══
            print(f"  [1/5] Generating idea ({tf})...")
            idea_prompt = build_idea_prompt(
                timeframe=tf,
                existing_strategies=portfolio.list(),
                round_num=round_num,
                total_rounds=n_strategies,
                tried_names=list(tried_strategies),
            )
            
            idea = chat.send_json(idea_prompt, retries=3)
            if idea is None:
                consecutive_errors += 1
                print(f"  ❌ Failed to generate idea (consecutive errors: {consecutive_errors})")
                
                # Rate limit detected → stop immediately
                if consecutive_errors >= 3:
                    print(f"\n  🛑 RATE LIMIT DETECTED — Stopping pipeline.")
                    print(f"     {stats['accepted']} strategies saved. Re-run later with fresh cookies.")
                    break
                
                stats['errors'] += 1
                continue
            
            consecutive_errors = 0  # Reset on success
            
            name = idea.get('name', f'Strategy_{round_num}')
            family = idea.get('family', 'unknown')
            description = idea.get('description', '')
            tried_strategies.add(name)
            stats['idea_generated'] += 1
            print(f"  ✅ Idea: {name} ({family})")
            print(f"     {description[:80]}")
            
            # ═══ STEP 2: Generate Code ═══
            print(f"  [2/5] Generating code...")
            code_prompt = build_code_prompt(idea)
            raw_code = chat.send(code_prompt)
            code = extract_code(raw_code)
            
            if not code or len(code) < 50:
                print(f"  ❌ Code too short ({len(code)} chars)")
                stats['errors'] += 1
                continue
            
            stats['code_generated'] += 1
            print(f"  ✅ Code generated ({len(code)} chars)")
            
            # ═══ STEP 3: Validate (with auto-fix) ═══
            print(f"  [3/5] Validating...")
            strategy_class = None
            
            for fix_attempt in range(3):
                cls, error = validate_strategy(code, data, verbose=verbose)
                
                if cls is not None:
                    strategy_class = cls
                    break
                
                if fix_attempt < 2:
                    print(f"  ⚠️  Validation failed (attempt {fix_attempt+1}): {error[:100]}")
                    print(f"  🔧 Asking LLM to fix...")
                    fix_prompt = build_fix_prompt(code, error, name)
                    raw_fix = chat.send(fix_prompt)
                    code = extract_code(raw_fix)
                else:
                    print(f"  ❌ Validation failed after 3 attempts: {error[:150]}")
            
            if strategy_class is None:
                stats['errors'] += 1
                _log_entry(log_path, {
                    'round': round_num, 'tf': tf, 'name': name,
                    'status': 'validation_failed', 'error': error[:300],
                    'timestamp': datetime.now().isoformat(),
                })
                continue
            
            actual_name = strategy_class.__name__
            if actual_name in ('MyStrategy', 'StrategyNameHere', 'CustomStrategy'):
                print(f"  ⚠️  LLM used template name '{actual_name}', renaming to '{name}'")
            
            stats['validation_passed'] += 1
            print(f"  ✅ Validated: {actual_name}")
            
            # ═══ STEP 4: Optimize ═══
            print(f"  [4/5] Optimizing ({n_trials} trials)...")
            param_space = _parse_param_space(idea.get('param_space', {}))
            
            if not param_space:
                # No param space -- just run with defaults
                engine = XNOBacktestEngine(**engine_config)
                strategy = strategy_class()
                result = engine.run(strategy, data)
                metrics = reporting.compute_metrics(result)
                best_params = strategy.params
            else:
                try:
                    optimizer = Optimizer(
                        strategy_class=strategy_class,
                        param_space=param_space,
                        data=data,
                        engine_config=engine_config,
                        objective=objective,
                        direction=direction,
                        method='bayesian',
                        n_trials=n_trials,
                        n_jobs=1,
                    )
                    opt_result = optimizer.run()
                    result = opt_result.best_result
                    metrics = reporting.compute_metrics(result)
                    best_params = opt_result.best_params
                except Exception as e:
                    print(f"  ❌ Optimization failed: {e}")
                    stats['errors'] += 1
                    _log_entry(log_path, {
                        'round': round_num, 'tf': tf, 'name': name,
                        'status': 'optimization_failed', 'error': str(e)[:300],
                        'timestamp': datetime.now().isoformat(),
                    })
                    continue
            
            stats['optimization_done'] += 1
            print(f"  ✅ Optimized | Sharpe={metrics.get('sharpe_ratio', 0):.2f} "
                  f"CAGR={metrics.get('cagr', 0)*100:.1f}% "
                  f"MDD={metrics.get('max_drawdown_pct', 0):.1f}% "
                  f"PF={metrics.get('profit_factor', 0):.2f} "
                  f"Trades={metrics.get('total_trades', 0)}")
            print(f"     Best params: {best_params}")
            
            # ═══ STEP 5: Portfolio Evaluation ═══
            print(f"  [5/5] Portfolio evaluation...")
            equity_curve = result.equity_curve
            
            accepted, reason = portfolio.evaluate_and_add(
                name=name,
                timeframe=tf,
                family=family,
                description=description,
                code=code,
                params=best_params,
                metrics=metrics,
                equity_curve=equity_curve,
            )
            
            if accepted:
                stats['accepted'] += 1
                print(f"  🎉 {reason}")
            else:
                if 'correlation' in reason:
                    stats['rejected_correlation'] += 1
                else:
                    stats['rejected_criteria'] += 1
                print(f"  ⛔ {reason}")
            
            # Log
            _log_entry(log_path, {
                'round': round_num, 'tf': tf, 'name': name,
                'family': family, 'params': best_params,
                'metrics': {k: round(v, 4) if isinstance(v, float) else v 
                           for k, v in metrics.items()},
                'status': 'accepted' if accepted else 'rejected',
                'reason': reason,
                'timestamp': datetime.now().isoformat(),
            })
            
        except Exception as e:
            stats['errors'] += 1
            print(f"  💥 Unexpected error: {type(e).__name__}: {e}")
            traceback.print_exc()
            _log_entry(log_path, {
                'round': round_num, 'tf': tf,
                'status': 'error', 'error': str(e)[:500],
                'timestamp': datetime.now().isoformat(),
            })
            continue
    
    # ── Final Summary ──
    total_time = time.time() - start_time
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    PIPELINE COMPLETE                       ║
╠══════════════════════════════════════════════════════════════╣
║  Total time:       {total_time/60:6.1f} minutes                       ║
║  Rounds attempted: {stats['total_attempts']:6d}                               ║
║  Ideas generated:  {stats['idea_generated']:6d}                               ║
║  Code generated:   {stats['code_generated']:6d}                               ║
║  Validation pass:  {stats['validation_passed']:6d}                               ║
║  Optimized:        {stats['optimization_done']:6d}                               ║
║  ─────────────────────────────────────────────────────────  ║
║  ✅ ACCEPTED:       {stats['accepted']:6d}                               ║
║  ⛔ Rejected (crit):{stats['rejected_criteria']:6d}                               ║
║  ⛔ Rejected (corr):{stats['rejected_correlation']:6d}                               ║
║  ❌ Errors:         {stats['errors']:6d}                               ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    portfolio.print_summary()
    
    # Cleanup
    chat.stop_keepalive()
    
    return portfolio, stats
