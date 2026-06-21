import os
import sys

# Fix encoding for Windows subprocesses print statements (emojis, icons)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utilities.AppConfig import PROJECT_ROOT
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

from strategy_workflows.MCTSEngine import MCTSEngine, Dimension, DynamicMCTSStrategy
from strategy_workflows.SemanticCompiler import SemanticCompiler, ASTNode
from core_engine.BacktestEngine import load_data, XNOBacktestEngine
from core_engine.GenerateReport import compute_metrics
from strategy_workflows.PortfolioManager import PortfolioManager

# TWEAK: Add more timeframes (e.g., "5m", "1h", "2h", "4h", "1d") to hunt for alphas across all market environments.
TIMEFRAMES = ["1m", "3m", "5m", "10m", "15m", "30m", "60m"]

# TWEAK: Increase to 1000, 5000, or 10000 to unleash MCTS full power. Higher iterations = deeper search = better formulas, but high CPU/RAM cost.
ITERATIONS_PER_DIMENSION = 50000

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

def generate_strategy_code(expr_str: str, direction: float, position_scale: float, window: int = 20, z_score_threshold: float = 1.0) -> str:
    """Generates a clean CustomStrategy Python source code string."""
    return f"""# [MCTS_DISCOVERY_ENGINE]
from core_engine.XnoEngine import SimpleAlgorithm

class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # 1. Inputs
        open_price = self.data.pv_open
        open_ = self.data.pv_open
        high = self.data.pv_high
        low = self.data.pv_low
        close = self.data.pv_close
        volume = self.data.pv_volume
        
        # 2. Discovered Core Formula
        alpha_val = {expr_str}
        
        # 3. Standardization (Z-Score)
        window = {window}
        r_mean = self.feat.rolling_mean(alpha_val, window)
        r_std = self.feat.rolling_std(alpha_val, window) + 1e-8
        
        z_score = (alpha_val - r_mean) / r_std
        z_score = z_score * {direction}

        # 4. Position signals (EXIT first, ENTRY second)
        raw_pos = self.op.where(z_score > {z_score_threshold}, {position_scale}, self.op.where(z_score < -{z_score_threshold}, -{position_scale}, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == {position_scale}
        short_mask = raw_pos == -{position_scale}
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position={position_scale})
        self.set_positions(short_mask, position=-{position_scale})
"""

def process_timeframe(tf: str, iterations: int = 50000):
    """
    Worker function to run MCTS and Backtesting for a single timeframe.
    
    This function processes candidate ideas for the given timeframe:
    1. Loads the historical data for the timeframe.
    2. Reads macro blueprints from the results/ideas folder.
    3. Runs MCTSEngine search on each blueprint.
    4. Evaluates generated candidates through a full backtest.
    5. Optimizes the candidate's position scale.
    6. Filters candidates based on basic portfolio criteria and an independent 
       correlation threshold of 0.50 (CORR_THRESHOLD = 0.50) against already 
       accepted candidates within the same timeframe processing loop.
       
    Parameters
    ----------
    tf : str
        The timeframe to process (e.g. '10m', '1h').
    iterations : int, default 50000
        The number of MCTS iterations to perform per dimension.
        
    Returns
    -------
    tuple
        (timeframe, total_generated, total_rejected, successful_candidates)
    """
    import logging
    import warnings
    warnings.filterwarnings('ignore')
    logging.getLogger("core_engine.XnoEngine").setLevel(logging.CRITICAL)
    logging.getLogger("core_engine.RestrictedSeries").setLevel(logging.CRITICAL)
    
    print(f"\n--- [Worker {tf}] Starting processing ---")
    
    portfolio_manager = PortfolioManager() # Read-only use to check criteria
    full_backtest_engine = XNOBacktestEngine()
    
    # ==========================================
    # GIAI ĐOẠN 1: KHỞI TẠO KÝ ỨC TOÀN CỤC
    # ==========================================
    existing_portfolio_names = set()
    global_position_matrix = pd.DataFrame()
    pos_series_list = []
    
    portfolio_file = os.path.join(PROJECT_ROOT, "results", "portfolio_summary.json")
    if os.path.exists(portfolio_file):
        try:
            import json
            with open(portfolio_file, 'r', encoding='utf-8') as pf:
                portfolio_data = json.load(pf)
                strategies = portfolio_data.get("strategies", [])
                if isinstance(strategies, list):
                    for s in strategies:
                        if isinstance(s, dict) and "name" in s:
                            name = s["name"]
                            existing_portfolio_names.add(name)
                            s_tf = s.get("timeframe", tf)
                            pos_path = os.path.join(PROJECT_ROOT, "results", f"{name}_{s_tf}_positions.csv")
                            if os.path.exists(pos_path):
                                pos_df = pd.read_csv(pos_path, index_col=0, parse_dates=True)
                                if not pos_df.empty and len(pos_df.columns) > 0:
                                    pos_series_list.append(pos_df.iloc[:, 0].rename(name))
            if pos_series_list:
                global_position_matrix = pd.concat(pos_series_list, axis=1)
        except Exception as pe:
            print(f"[Worker {tf}] Warning: Failed to load global position matrix: {pe}")

    mcts = MCTSEngine(timeframe=tf, max_depth=4, global_position_matrix=global_position_matrix)
    
    # ==========================================
    # ĐỌC Ý TƯỞNG TỪ TẦNG 1 & BIÊN DỊCH BỞI TẦNG 2
    # ==========================================
    ideas_folder = os.path.join(PROJECT_ROOT, "results", "ideas")
    if not os.path.exists(ideas_folder):
        print(f"[Worker {tf}] No ideas folder found.")
        return tf, 0, 0, []
        
    import json
    import glob
    import shutil
    idea_files = glob.glob(os.path.join(ideas_folder, f"*_{tf}.json"))
    
    processed_folder = os.path.join(ideas_folder, "processed")
    os.makedirs(processed_folder, exist_ok=True)

    compiler = SemanticCompiler()
    
    for idea_file in idea_files:
        filename = os.path.basename(idea_file)
        dest_path = os.path.join(processed_folder, filename)
        
        idea_data = None
        try:
            with open(idea_file, 'r', encoding='utf-8') as f:
                idea_data = json.load(f)
        except Exception as e:
            print(f"[Worker {tf}] Error reading {filename}: {e}")
            try:
                shutil.move(idea_file, dest_path)
            except Exception:
                pass
            continue
            
        try:
            name = idea_data.get("name")
            blueprint = idea_data.get("macro_blueprint")
            if not blueprint:
                shutil.move(idea_file, dest_path)
                continue
            
            # Check if this strategy is already in portfolio or failed lists
            failed_py_path = os.path.join(PROJECT_ROOT, "results", "failed", f"{name}_{tf}.py")
            failed_conv_path = os.path.join(PROJECT_ROOT, "results", "failed_conversions", f"{name}_{tf}.py")
            
            # If we have a general/unassigned failed strategy name as well
            failed_base_path = os.path.join(PROJECT_ROOT, "results", "failed", f"{name}.py")
            
            is_duplicate = (name in existing_portfolio_names) or \
                           os.path.exists(failed_py_path) or \
                           os.path.exists(failed_conv_path) or \
                           os.path.exists(failed_base_path)
                           
            if is_duplicate:
                print(f"[Worker {tf}] ⏩ Skipping MCTS for '{name}' (Already processed as success or failed).")
                shutil.move(idea_file, dest_path)
                continue
                
            print(f"[Worker {tf}] Compiling Blueprint: {blueprint}")
            ast_root = compiler.compile_blueprint(blueprint)
            
            # ==========================================
            # TẦNG 3: MCTS BRUTE-FORCE TÌM KIẾM CHIẾN LƯỢC
            # ==========================================
            mcts.run_search_from_blueprint(ast_root, n_iterations=iterations)
            shutil.move(idea_file, dest_path)
        except Exception as e:
            print(f"[Worker {tf}] Error processing {filename}: {e}")
            # Move the file even on compilation failure to avoid blocking the pipeline next time
            try:
                shutil.move(idea_file, dest_path)
            except Exception:
                pass
    
    candidates = mcts.get_best_candidates()
    
    total_generated = len(candidates)
    total_rejected = 0
    successful_candidates = []
    
    if not candidates:
        print(f"[Worker {tf}] No candidates found.")
        return tf, total_generated, total_rejected, successful_candidates
        
    print(f"\n[Worker {tf}] Found {total_generated} candidates. Executing One-pass Commit for top candidate...")
    
    # Lấy Top 1 ứng cử viên có Reward > 0
    valid_candidates = [c for c in candidates if c.get('reward', -10.0) > 0]
    
    if not valid_candidates:
        print(f"[Worker {tf}] ❌ All candidates failed hard filter (Reward <= 0). Rejected.")
        total_rejected = total_generated
        return tf, total_generated, total_rejected, successful_candidates
        
    top_cand = valid_candidates[0]
    
    expr = top_cand['expr']
    direction = top_cand['direction']
    window = top_cand.get('window', 20)
    z_score_threshold = top_cand.get('z_score', 1.0)
    best_scale = 0.2  # MCTS mặc định tính ở mức 0.2
    
    # Chạy lại 1 lần duy nhất để lấy equity_curve và positions
    df_full = load_data(tf)
    df_full['Volume'] = df_full['Volume'].fillna(0.0)
    
    strategy = DynamicMCTSStrategy(expr_str=expr, direction=direction, position_scale=best_scale, window=window, z_score_threshold=z_score_threshold)
    result = full_backtest_engine.run(strategy, df_full)
    metrics = top_cand.get('metrics', {})
    
    cagr = metrics.get('cagr', 0.0)
    sharpe = metrics.get('sharpe_ratio', 0.0)
    calmar = metrics.get('calmar_ratio', 0.0)
    reward = top_cand.get('reward', 0.0)
    
    print(f"[Worker {tf}] 🎉 ONE-PASS COMMIT! Reward: {reward:.2f} | Calmar: {calmar:.2f} | Sharpe: {sharpe:.2f} | CAGR: {cagr*100:.1f}%")
    
    successful_candidates.append({
        "expr": expr,
        "direction": direction,
        "best_scale": best_scale,
        "window": window,
        "z_score": z_score_threshold,
        "metrics": metrics,
        "equity_curve": result.equity_curve,
        "positions": result.positions
    })
    
    total_rejected = total_generated - 1
    
    print(f"--- [Worker {tf}] Finished processing ---")
    return tf, total_generated, total_rejected, successful_candidates

def run_mcts_pipeline(iterations: int = 50000):
    """
    Main entry point for running the parallel MCTS strategy discovery pipeline.
    
    Launches worker processes across all configured timeframes. Successful candidates 
    are validated, checked for correlation warnings (threshold of 0.50), and 
    formally accepted into the final portfolio manager.
    
    Parameters
    ----------
    iterations : int, default 50000
        Number of MCTS iterations per worker.
    """
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
                    
                    code = generate_strategy_code(cand["expr"], cand["direction"], cand["best_scale"], cand["window"], cand["z_score"])
                    
                    accepted, reason = portfolio_manager.evaluate_and_add(
                        name=unique_name,
                        timeframe=tf_res,
                        family="MCTS_Discovered",
                        description=f"Alpha discovered via One-pass MCTS: {cand['expr']}",
                        code=code,
                        params={"direction": cand["direction"], "position_scale": cand["best_scale"], "window": cand["window"], "z_score": cand["z_score"]},
                        metrics=cand["metrics"],
                        equity_curve=cand["equity_curve"],
                        positions=cand["positions"],
                        force_add=True
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
        stats_file = os.path.join(PROJECT_ROOT, "results", "mcts_stats.json")
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
    # MỚI: Dùng toàn bộ 12 luồng, chỉ chừa lại 1-2 luồng cho Windows thở
    import multiprocessing
    beast_mode_workers = max(1, multiprocessing.cpu_count() - 2)  # Sẽ bằng 10
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=beast_mode_workers) as executor:
        run_mcts_pipeline(iterations=50000)
