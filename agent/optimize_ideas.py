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
from agent.templates import TEMPLATE_REGISTRY
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

def clamp_params(template_name: str, params: dict) -> dict:
    if template_name not in TEMPLATE_REGISTRY:
        return params
        
    template_info = TEMPLATE_REGISTRY[template_name]
    clamped = {}
    for p_name, p_info in template_info["params"].items():
        val = params.get(p_name)
        if val is None:
            val = p_info["default"]
            
        try:
            if p_info["type"] == "int":
                val = int(round(float(val)))
            elif p_info["type"] == "float":
                val = float(val)
        except Exception:
            val = p_info["default"]
            
        low = p_info["low"]
        high = p_info["high"]
        if val < low:
            val = low
        elif val > high:
            val = high
            
        clamped[p_name] = val
    return clamped

def run_optimization():
    ideas_dir = os.path.join(PROJECT_ROOT, "agent", "results", "ideas")
    output_dir = os.path.join(PROJECT_ROOT, "agent", "results")
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "failed_conversions"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "pushed"), exist_ok=True)
    
    if not os.path.exists(ideas_dir):
        print(f"Error: ideas directory not found at {ideas_dir}")
        sys.exit(1)
        
    json_files = [f for f in os.listdir(ideas_dir) if f.endswith('.json')]
    print(f"Found {len(json_files)} strategy ideas to optimize/convert.")
    
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
            print(f"Skipping {filename} - already optimized/converted.")
            continue
            
        print(f"\nProcessing {filename}...")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                idea = json.load(f)
                
            template_name = idea.get('template_name')
            if not template_name or template_name not in TEMPLATE_REGISTRY:
                print(f"  ❌ Unknown template '{template_name}'. Skipping.")
                fail_count += 1
                continue
                
            tf = idea.get('timeframe', '10m')
            params = idea.get('parameters', {})
            
            # Apply initial bounds check
            params = clamp_params(template_name, params)
            template = TEMPLATE_REGISTRY[template_name]
            
            # Temporary python file path for backtesting
            temp_py_filepath = os.path.join(output_dir, f"{idea.get('name')}_{tf}_temp.py")
            
            best_sharpe = -999.0
            best_cagr = 0.0
            best_params = params.copy()
            best_metrics = {}
            
            # 1. Run initial backtest with the LLM's suggested parameters
            print(f"  [Initial Run] Testing parameters: {params}")
            code = template['generate_code'](params)
            with open(temp_py_filepath, 'w', encoding='utf-8') as f:
                f.write(code)
                
            try:
                metrics = emulator.get_metrics(temp_py_filepath, tf)
                best_sharpe = metrics.get('sharpe_ratio', 0.0)
                best_cagr = metrics.get('cagr', 0.0)
                best_metrics = metrics.copy()
                print(f"    -> Backtest result: Sharpe={best_sharpe:.4f} | CAGR={best_cagr*100:.2f}%")
            except Exception as e:
                print(f"    ❌ Backtest crash: {e}")
                
            # 2. If target not met (Sharpe > 1.3 and CAGR > 15%), run Optuna optimization
            if not (best_sharpe > 1.3 and best_cagr > 0.15):
                print(f"  [Optuna] Initial parameters did not meet target (Sharpe > 1.3 & CAGR > 15%). Starting Optuna study...")
                
                def objective(trial):
                    trial_params = {}
                    for p_name, p_info in template['params'].items():
                        if p_info['type'] == 'int':
                            trial_params[p_name] = trial.suggest_int(p_name, p_info['low'], p_info['high'])
                        elif p_info['type'] == 'float':
                            trial_params[p_name] = trial.suggest_float(p_name, p_info['low'], p_info['high'])
                            
                    # Generate python code
                    trial_code = template['generate_code'](trial_params)
                    with open(temp_py_filepath, 'w', encoding='utf-8') as f:
                        f.write(trial_code)
                        
                    # Run backtest
                    try:
                        trial_metrics = emulator.get_metrics(temp_py_filepath, tf)
                        trial_sharpe = trial_metrics.get('sharpe_ratio', 0.0)
                        trial_cagr = trial_metrics.get('cagr', 0.0)
                        
                        trial.set_user_attr("cagr", trial_cagr)
                        trial.set_user_attr("metrics", trial_metrics)
                        return trial_sharpe
                    except Exception:
                        return -999.0
                        
                def stop_early_callback(study, trial):
                    if trial.value is not None and trial.value > 1.3:
                        cagr = trial.user_attrs.get("cagr", 0.0)
                        if cagr > 0.15:
                            print(f"  🎯 Target achieved early on trial {trial.number}! (Sharpe={trial.value:.4f}, CAGR={cagr*100:.2f}%)")
                            study.stop()
                            
                study = optuna.create_study(direction="maximize")
                study.optimize(objective, n_trials=20, callbacks=[stop_early_callback])
                
                # Retrieve best results from study
                if len(study.trials) > 0 and study.best_value is not None:
                    trial_best_sharpe = study.best_value
                    trial_best_cagr = study.best_trial.user_attrs.get("cagr", 0.0)
                    if trial_best_sharpe > best_sharpe:
                        best_sharpe = trial_best_sharpe
                        best_cagr = trial_best_cagr
                        best_params = study.best_params.copy()
                        best_metrics = study.best_trial.user_attrs.get("metrics", {}).copy()
            else:
                print(f"  🎯 Target achieved on initial run!")
            
            # Clean up temp file
            if os.path.exists(temp_py_filepath):
                os.remove(temp_py_filepath)
                
            # Check if best run meets target criteria
            if best_sharpe > 1.3 and best_cagr > 0.15:
                print(f"  ✅ Optimization Success! Final Sharpe: {best_sharpe:.4f} | CAGR: {best_cagr*100:.2f}%")
                # Write final python code with best parameters
                final_code = template['generate_code'](best_params)
                with open(py_filepath, 'w', encoding='utf-8') as f:
                    f.write(final_code)
                print(f"  💾 Saved optimized strategy to {py_filepath}")
                success_count += 1
            else:
                print(f"  ❌ Optimization Failed: Best Sharpe={best_sharpe:.4f} did not meet target criteria.")
                # Save best failed code to failed_conversions
                failed_code = template['generate_code'](best_params)
                with open(failed_filepath, 'w', encoding='utf-8') as f:
                    f.write(failed_code)
                print(f"  💾 Saved failed attempt to failed_conversions/{py_filename}")
                fail_count += 1
                
        except Exception as e:
            print(f"  💥 Exception processing {filename}: {e}")
            traceback.print_exc()
            fail_count += 1
            
    print("\n" + "="*50)
    print(f"Optimization and Conversion Complete!")
    print(f"Successful optimized strategies: {success_count}")
    print(f"Failed to optimize: {fail_count}")
    print("="*50)

if __name__ == "__main__":
    run_optimization()
