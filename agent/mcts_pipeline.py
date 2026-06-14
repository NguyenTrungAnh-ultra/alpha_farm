# MCTS Pipeline for Alpha Farm
# Runs MCTS searches across multiple timeframes, filters candidate alphas
# against portfolio criteria, and saves successful candidates.

import os
import sys
import time
import re
import pandas as pd
import concurrent.futures
from typing import List, Dict, Any

PROJECT_ROOT = "f:/Projects/alpha_farm"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.mcts_engine import MCTSEngine, Dimension, ASTNode, DynamicMCTSStrategy
from backtest.engine import load_data, XNOBacktestEngine
from backtest.reporting import compute_metrics
from agent.portfolio import PortfolioManager

# TWEAK: Add more timeframes (e.g., "5m", "1h", "2h", "4h", "1d") to hunt for alphas across all market environments.
TIMEFRAMES = ["1m", "3m", "5m", "10m", "15m", "30m", "60m"]

# TWEAK: Increase to 1000, 5000, or 10000 to unleash MCTS full power. Higher iterations = deeper search = better formulas, but high CPU/RAM cost.
ITERATIONS_PER_DIMENSION = 10000

# TWEAK: Add smaller/larger scales (e.g., [0.05, 0.1, ..., 0.5]) to give the engine more flexibility in risk management.
POSITION_SCALES = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]

def generate_descriptive_name(expr_str: str) -> str:
    """Generates a technical, functional name based on indicator and features."""
    indicators = re.findall(r"self\.feat\.([a-zA-Z0-9_]+)", expr_str)
    if not indicators:
        indicators = re.findall(r"\b(close|open|high|low|volume)\b", expr_str)
    
    words = [w.capitalize() for w in indicators]
    if not words:
        words = ["Formula"]
        
    name = "Mcts_" + "_".join(words[:3])
    # Remove duplicates in name if any
    seen = set()
    unique_words = []
    for w in name.split('_'):
        if w not in seen:
            seen.add(w)
            unique_words.append(w)
    return "_".join(unique_words)

def generate_strategy_code(expr_str: str, direction: float, position_scale: float) -> str:
    """Generates a clean CustomStrategy Python source code string."""
    return f"""# [MCTS_DISCOVERY_ENGINE]
from xno_sdk.engine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Inputs
        open_price = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        
        # 2. Discovered Core Formula
        alpha_val = {expr_str}
        
        # 3. Standardization
        window = 120
        r_min = self.feat.rolling_min(alpha_val, window)
        r_max = self.feat.rolling_max(alpha_val, window)
        scaled = (alpha_val - r_min) / (r_max - r_min + 1e-8)
        scaled = (scaled - 0.5) * 2.0
        
        # Direction
        scaled = scaled * {direction}
        
        # 4. Position signals (EXIT first, ENTRY second)
        raw_pos = self.op.where(scaled > 0.5, {position_scale}, self.op.where(scaled < -0.5, -{position_scale}, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == {position_scale}
        short_mask = raw_pos == -{position_scale}
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position={position_scale})
        self.set_positions(short_mask, position=-{position_scale})
"""

def process_timeframe(tf: str, iterations: int = 10000):
    """Worker function to run MCTS and Backtesting for a single timeframe."""
    print(f"\n--- [Worker {tf}] Starting processing ---")
    
    # Instantiate isolated engines for this process
    portfolio_manager = PortfolioManager() # Read-only use to check criteria
    full_backtest_engine = XNOBacktestEngine()
    
    mcts = MCTSEngine(timeframe=tf, max_depth=4)
    
    # Search dimensions
    mcts.run_search(Dimension.RATIO, n_iterations=iterations)
    mcts.run_search(Dimension.CURRENCY, n_iterations=iterations)
    mcts.run_search(Dimension.VOLUME, n_iterations=iterations)
    
    candidates = mcts.get_best_candidates()
    
    total_generated = len(candidates)
    total_rejected = 0
    successful_candidates = []
    
    if not candidates:
        print(f"[Worker {tf}] No candidates found.")
        return tf, total_generated, total_rejected, successful_candidates
        
    print(f"\n[Worker {tf}] Found {total_generated} candidates. Running full 5-year backtests with scale optimization...")
    
    df_full = load_data(tf)
    df_full['Volume'] = df_full['Volume'].fillna(0.0)
    
    for cand in candidates:
        expr = cand['expr']
        direction = cand['direction']
        param_count = cand['param_count']
        
        if param_count > 6:
            print(f"[Worker {tf}] Skipping {expr}: too many parameters ({param_count} > 6).")
            total_rejected += 1
            continue
            
        best_scale = None
        best_metrics = None
        best_result = None
        best_sharpe = -999.0
        
        for scale in POSITION_SCALES:
            try:
                strategy = DynamicMCTSStrategy(expr_str=expr, direction=direction, position_scale=scale)
                result = full_backtest_engine.run(strategy, df_full)
                metrics = compute_metrics(result)
                
                # Check criteria
                passed, reasons = portfolio_manager.meets_criteria(metrics)
                
                # We still evaluate correlation for logs but we don't reject
                max_corr_returns = portfolio_manager.compute_max_correlation(result.equity_curve)
                max_corr_positions = portfolio_manager.compute_max_position_correlation(result.positions)
                max_corr = max(max_corr_returns, max_corr_positions)
                
                # Find the scale with the highest Sharpe, but ONLY if it passes the extreme V2 filter
                current_sharpe = metrics.get('sharpe_ratio', -999.0)
                if passed and current_sharpe > best_sharpe:
                    best_sharpe = current_sharpe
                    best_scale = scale
                    best_metrics = metrics
                    best_result = result
            except Exception as e:
                pass
                
        if best_scale is not None and best_result is not None:
            cagr = best_metrics.get('cagr', 0.0)
            print(f"[Worker {tf}] 🎉 FOUND VALID MATH & PERFORMANCE! Best scale {best_scale} -> Sharpe: {best_sharpe:.2f} | CAGR: {cagr*100:.1f}%")
            
            successful_candidates.append({
                "expr": expr,
                "direction": direction,
                "best_scale": best_scale,
                "metrics": best_metrics,
                "equity_curve": best_result.equity_curve,
                "positions": best_result.positions
            })
            # No break! We want all candidates.
        else:
            print(f"[Worker {tf}] ❌ Formula failed performance criteria (Sharpe > 1.3, CAGR > 15%) or mathematically failed on all scales.")
            total_rejected += 1
            
    print(f"--- [Worker {tf}] Finished processing ---")
    return tf, total_generated, total_rejected, successful_candidates

def run_mcts_pipeline(iterations: int = 10000):
    print("==============================================================")
    print("      STARTING MULTIPROCESSING MCTS ALPHA SEARCH PIPELINE     ")
    print("==============================================================")
    
    portfolio_manager = PortfolioManager()
    
    total_discovered = 0
    total_generated = 0
    total_rejected = 0
    
    # Launch parallel workers
    with concurrent.futures.ProcessPoolExecutor(max_workers=len(TIMEFRAMES)) as executor:
        futures = {executor.submit(process_timeframe, tf, iterations): tf for tf in TIMEFRAMES}
        
        for future in concurrent.futures.as_completed(futures):
            tf = futures[future]
            try:
                tf_res, gen, rej, successful = future.result()
                total_generated += gen
                total_rejected += rej
                
                # Aggregate successful candidates into Portfolio
                for cand in successful:
                    import uuid
                    name = generate_descriptive_name(cand["expr"])
                    uid = uuid.uuid4().hex[:4]
                    unique_name = f"{name}_{uid}"
                    
                    code = generate_strategy_code(cand["expr"], cand["direction"], cand["best_scale"])
                    
                    accepted, reason = portfolio_manager.evaluate_and_add(
                        name=unique_name,
                        timeframe=tf_res,
                        family="MCTS_Discovered",
                        description=f"Alpha discovered via MCTS: {cand['expr']}",
                        code=code,
                        params={"direction": cand["direction"], "position_scale": cand["best_scale"]},
                        metrics=cand["metrics"],
                        equity_curve=cand["equity_curve"],
                        positions=cand["positions"]
                    )
                    
                    print(f"[Main] Saving {tf_res} candidate {unique_name}: {reason}")
                    if accepted:
                        total_discovered += 1
                        
            except Exception as e:
                print(f"[Main] Timeframe {tf} generated an exception: {e}")
                import traceback
                traceback.print_exc()

    print("\n==============================================================")
    print(f" MCTS SEARCH PIPELINE COMPLETE | Discovered: {total_discovered} alphas")
    print(f" Generated Candidates: {total_generated} | Rejected: {total_rejected}")
    print("==============================================================")

    # Save stats
    try:
        import json
        from datetime import datetime
        stats_file = os.path.join(PROJECT_ROOT, "agent", "results", "mcts_stats.json")
        stats = []
        if os.path.exists(stats_file):
            with open(stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
        stats.append({
            "timestamp": datetime.now().isoformat(),
            "total_generated": total_generated,
            "total_rejected": total_rejected,
            "total_discovered": total_discovered
        })
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=4)
    except Exception as e:
        print(f"Failed to save stats: {e}")

if __name__ == "__main__":
    run_mcts_pipeline()
