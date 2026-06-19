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
        window = 20
        r_mean = self.feat.rolling_mean(alpha_val, window)
        r_std = self.feat.rolling_std(alpha_val, window) + 1e-8
        
        z_score = (alpha_val - r_mean) / r_std
        z_score = z_score * {direction}

        # 4. Position signals (EXIT first, ENTRY second)
        raw_pos = self.op.where(z_score > 1.0, {position_scale}, self.op.where(z_score < -1.0, -{position_scale}, 0.0))
        
        flat_mask = raw_pos == 0.0
        long_mask = raw_pos == {position_scale}
        short_mask = raw_pos == -{position_scale}
        
        self.set_positions(flat_mask, position=0.0)
        self.set_positions(long_mask, position={position_scale})
        self.set_positions(short_mask, position=-{position_scale})
"""

def process_timeframe(tf: str, iterations: int = 10000):
    """Worker function to run MCTS and Backtesting for a single timeframe."""
    import logging
    import warnings
    warnings.filterwarnings('ignore')
    logging.getLogger("core_engine.XnoEngine").setLevel(logging.CRITICAL)
    logging.getLogger("core_engine.RestrictedSeries").setLevel(logging.CRITICAL)
    
    print(f"\n--- [Worker {tf}] Starting processing ---")
    
    # Instantiate isolated engines for this process
    portfolio_manager = PortfolioManager() # Read-only use to check criteria
    full_backtest_engine = XNOBacktestEngine()
    
    mcts = MCTSEngine(timeframe=tf, max_depth=4)
    
    # ==========================================
    # ĐỌC Ý TƯỞNG TỪ TẦNG 1 & BIÊN DỊCH BỞI TẦNG 2
    # ==========================================
    ideas_folder = os.path.join(PROJECT_ROOT, "results", "ideas")
    if not os.path.exists(ideas_folder):
        print(f"[Worker {tf}] No ideas folder found.")
        return tf, 0, 0, []
        
    import json
    import glob
    idea_files = glob.glob(os.path.join(ideas_folder, f"*_{tf}.json"))
    
    compiler = SemanticCompiler()
    
    for idea_file in idea_files:
        with open(idea_file, 'r', encoding='utf-8') as f:
            try:
                idea_data = json.load(f)
                blueprint = idea_data.get("macro_blueprint")
                if not blueprint:
                    continue
                    
                print(f"[Worker {tf}] Compiling Blueprint: {blueprint}")
                ast_root = compiler.compile_blueprint(blueprint)
                
                # ==========================================
                # TẦNG 3: MCTS BRUTE-FORCE TÌM KIẾM CHIẾN LƯỢC
                # ==========================================
                mcts.run_search_from_blueprint(ast_root, n_iterations=iterations)
            except Exception as e:
                print(f"[Worker {tf}] SemanticCompiler Error: {e}")
    
    candidates = mcts.get_best_candidates()
    
    total_generated = len(candidates)
    total_rejected = 0
    successful_candidates = []
    
    # ==========================================
    # PHẪU THUẬT 2: Khởi tạo Bộ nhớ Ngắn hạn
    # Lưu trữ đường cong vốn của các chiến lược đã đỗ
    # ==========================================
    local_accepted_curves = [] 
    
    if not candidates:
        print(f"[Worker {tf}] No candidates found.")
        return tf, total_generated, total_rejected, successful_candidates
        
    print(f"\n[Worker {tf}] Found {total_generated} candidates. Running full 5-year backtests with scale optimization...")
    
    df_full = load_data(tf, start='2020-01-01', end='2023-12-31')
    df_full['Volume'] = df_full['Volume'].fillna(0.0)
    
    for cand in candidates:
        expr = cand['expr']
        direction = cand['direction']
            
        best_scale = None
        best_metrics = None
        best_result = None
        best_sharpe = -999.0
        
        for scale in POSITION_SCALES:
            try:
                strategy = DynamicMCTSStrategy(expr_str=expr, direction=direction, position_scale=scale)
                result = full_backtest_engine.run(strategy, df_full)
                metrics = compute_metrics(result)
                
                passed, reasons = portfolio_manager.meets_criteria(metrics)
                
                # ==========================================
                # PHẪU THUẬT 3: Máy chém Tương quan Động
                # So sánh chiến lược hiện tại với sổ tay bộ nhớ
                # ==========================================
                max_corr = 0.0
                if local_accepted_curves:
                    correlations = []
                    for hist_curve in local_accepted_curves:
                        # Ghép nối 2 đường cong vốn để loại bỏ giá trị NaN
                        valid_df = pd.DataFrame({'curr': result.equity_curve, 'hist': hist_curve}).dropna()
                        # Đảm bảo có đủ dữ liệu và có phương sai (chống lỗi ConstantInput)
                        if len(valid_df) > 20 and valid_df['curr'].std() > 0 and valid_df['hist'].std() > 0:
                            corr_value = valid_df['curr'].corr(valid_df['hist'])
                            correlations.append(corr_value)
                    
                    if correlations:
                        max_corr = max(correlations)
                
                # Cài đặt ngưỡng loại bỏ khắc nghiệt (Ví dụ: 0.70)
                CORR_THRESHOLD = 0.70
                current_sharpe = metrics.get('sharpe_ratio', -999.0)
                
                # Phải thỏa mãn cả 3: Đỗ tiêu chuẩn CƠ BẢN + Độc lập + Sharpe TỐT NHẤT
                if passed and (max_corr < CORR_THRESHOLD) and (current_sharpe > best_sharpe):
                    best_sharpe = current_sharpe
                    best_scale = scale
                    best_metrics = best_metrics = metrics
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
            
            # KẾT THÚC PHẪU THUẬT 3: Lưu lại bằng chứng vào sổ tay bộ nhớ
            local_accepted_curves.append(best_result.equity_curve)
            
        else:
            print(f"[Worker {tf}] ❌ Formula failed performance or correlation criteria (> 0.70).")
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
        run_mcts_pipeline(iterations=30000)
