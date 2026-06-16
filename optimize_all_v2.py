import glob
import os
import re
import pandas as pd
from typing import Dict, Any

from backtest.optimizer_v2 import XNOOptimizerV2
from xno_sdk.emulator import XNOPlatformEmulator
from backtest import reporting

def generate_param_space(filepath: str) -> Dict[str, Any]:
    """Tự động phân tích code và sinh ra không gian tìm kiếm (param_space) cho Optuna."""
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()
        
    param_space = {}
    
    # Pattern: self.window = int(self.window if 'window' in self.__dict__ else 20)
    pattern = r"self\.([a-zA-Z0-9_]+)\s*=\s*(int|float)\(self\.\1\s+if.+else\s+([\d\.]+)\)"
    matches = re.findall(pattern, code)
    
    for name, ptype, default_val_str in matches:
        name_lower = name.lower()
        if ptype == 'int':
            default_val = int(default_val_str)
            
            # Sử dụng tập hợp cố định cho các tham số chu kỳ
            if any(k in name_lower for k in ['window', 'timeperiod', 'period', 'length']):
                param_space[name] = [5, 10, 20, 30, 50, 60, 100, 200]
            else:
                # Phạm vi: [default/2, default*2]
                low = max(2, default_val // 2)
                high = default_val * 2
                
                # Làm tròn range nếu số lớn
                if default_val > 10:
                    low = (low // 5) * 5
                    high = ((high + 4) // 5) * 5
                
                step = 1 if default_val <= 10 else 2
                param_space[name] = (low, high, step)
            
        elif ptype == 'float':
            default_val = float(default_val_str)
            
            # Tập hợp cho các tham số multiplier, std_dev, factor...
            if any(k in name_lower for k in ['multiplier', 'std_dev', 'stddev', 'deviation', 'factor', 'sigma']):
                param_space[name] = [1.0, 1.5, 2.0, 2.5, 3.0]
            else:
                # Phạm vi: [default*0.5, default*1.5]
                if default_val == 0.0:
                    low, high, step = 0.0, 1.0, 0.1
                else:
                    low = default_val * 0.5
                    high = default_val * 1.5
                    step = default_val * 0.1
                    
                    # Round cho đẹp
                    low = round(low, 2)
                    high = round(high, 2)
                    step = round(step, 2)
                    if step == 0.0:
                        step = 0.01
                        
                param_space[name] = (low, high, step)
                
    return param_space

def main():
    target_dirs = [
        "agent/results/",
        "agent/results/pushed/"
    ]
    
    files_to_optimize = []
    
    for d in target_dirs:
        py_files = glob.glob(f"{d}/*.py")
        for f in py_files:
            basename = os.path.basename(f)
            # Bỏ qua alpha 101 raw
            if "alpha_101" in basename.lower() or "wq_alpha" in basename.lower():
                continue
                
            files_to_optimize.append(f)
            
    # Lọc bỏ trùng lặp (lấy file trong pushed nếu có cả 2)
    files_dict = {}
    for f in files_to_optimize:
        files_dict[os.path.basename(f)] = f
    unique_files = list(files_dict.values())
    
    print(f"Found {len(unique_files)} valid strategies.")
    
    results = []
    emulator = XNOPlatformEmulator(verbose=False)
    
    for i, filepath in enumerate(unique_files, 1):
        basename = os.path.basename(filepath)
        print(f"\n[{i}/{len(unique_files)}] Processing: {basename}")
        
        # Kiểm tra xem file đã được tối ưu chưa
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if "# OPTIMIZATION_V2_COMPLETED" in content:
                print(f"  [!] Already optimized, skipping.")
                continue
                
        # Xác định timeframe
        tf_match = re.search(r'_(\d+m)\.py', basename)
        if not tf_match:
            print(f"  [!] Timeframe not found in filename, skipping.")
            continue
        timeframe = tf_match.group(1)
        
        # Sinh param_space
        param_space = generate_param_space(filepath)
        if not param_space:
            print(f"  [!] No flexible parameters found, benchmarking only.")
            try:
                metrics = emulator.get_metrics(filepath, timeframe)
                results.append({
                    "strategy": basename,
                    "timeframe": timeframe,
                    "status": "benchmark_only",
                    "obj_before": metrics.get("total_return_pct", 0.0),
                    "obj_after": metrics.get("total_return_pct", 0.0),
                    "trades": metrics.get("total_trades", 0),
                    "cagr": metrics.get("cagr", 0.0),
                    "best_params": ""
                })
                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write("\n\n# OPTIMIZATION_V2_COMPLETED\n")
            except Exception as e:
                print(f"  [!] Benchmark error: {e}")
            continue
            
        # Lấy base metrics trước khi tối ưu
        try:
            base_metrics = emulator.get_metrics(filepath, timeframe)
            obj_before = base_metrics.get("total_return_pct", 0.0)
        except Exception as e:
            print(f"  [!] Base metrics error: {e}")
            obj_before = 0.0
            
        print(f"  > Param space: {param_space}")
        print(f"  > Initial Objective: {obj_before:.4f}")
        
        # Chạy Optuna V2 (30 trials)
        try:
            opt = XNOOptimizerV2(
                filepath=filepath,
                timeframe=timeframe,
                param_space=param_space,
                n_trials=30,
                objective='total_return_pct'
            )
            study = opt.run()
            obj_after = study.best_value
            best_params = study.best_params
            
            # Đo lại metrics sau khi đã ghi đè code
            final_metrics = emulator.get_metrics(filepath, timeframe)
            
            final_sharpe = final_metrics.get("sharpe_ratio", 0.0)
            final_cagr = final_metrics.get("cagr", 0.0)
            
            if final_sharpe > 1.3 and final_cagr > 0.15:
                results.append({
                    "strategy": basename,
                    "timeframe": timeframe,
                    "status": "optimized",
                    "obj_before": obj_before,
                    "obj_after": obj_after,
                    "trades": final_metrics.get("total_trades", 0),
                    "cagr": final_cagr,
                    "best_params": str(best_params)
                })
                
                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write("\n\n# OPTIMIZATION_V2_COMPLETED\n")
            else:
                print(f"  [!] Optimized strategy failed V2 filter (Sharpe={final_sharpe:.4f}, CAGR={final_cagr*100:.1f}%). Deleting file.")
                if os.path.exists(filepath):
                    os.remove(filepath)
                results.append({
                    "strategy": basename,
                    "timeframe": timeframe,
                    "status": "failed_v2_filter",
                    "obj_before": obj_before,
                    "obj_after": obj_after,
                    "trades": final_metrics.get("total_trades", 0),
                    "cagr": final_cagr,
                    "best_params": str(best_params)
                })
            
        except Exception as e:
            print(f"  [!] Optimization error: {e}")
            results.append({
                "strategy": basename,
                "timeframe": timeframe,
                "status": f"error: {e}",
                "obj_before": obj_before if 'obj_before' in locals() else None,
                "obj_after": None,
                "trades": 0,
                "cagr": 0.0,
                "best_params": ""
            })
            
    # In báo cáo tổng kết
    print(f"\n{'='*80}")
    print("BATCH OPTIMIZATION REPORT (V2 EMULATOR)")
    print(f"{'='*80}")
    
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        df_success = df_res[~df_res['status'].str.startswith('error', na=False)].copy()
        
        if not df_success.empty:
            df_success['improvement'] = df_success['obj_after'] - df_success['obj_before']
            df_success = df_success.sort_values(by='obj_after', ascending=False)
            
            print(df_success[['strategy', 'timeframe', 'obj_before', 'obj_after', 'improvement', 'trades', 'cagr']].to_string(index=False))
            
            df_success.to_csv("agent/results/optuna_v2_report.csv", index=False)
            print("\nSaved detailed report to: agent/results/optuna_v2_report.csv")
        else:
            print("All strategies failed.")
    else:
        print("No results.")

if __name__ == "__main__":
    main()
