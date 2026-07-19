import os
import sys
import glob
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core_engine.BacktestEngine import load_data
from core_engine.PlatformEmulator import XNOPlatformEmulator
from regime_tagging_research.run_hmm_monte_carlo_validation import fit_hmm_model

def main():
    emulator = XNOPlatformEmulator()
    
    # Read the existing validation results to know which alphas to analyze
    val_csv = os.path.join(PROJECT_ROOT, "regime_tagging_research", "all_alphas_validation_results.csv")
    if not os.path.exists(val_csv):
        print("Validation CSV not found!")
        return
    val_df = pd.read_csv(val_csv)
    valid_strategies = set(val_df['Strategy'].values)
    
    all_py_files = glob.glob(os.path.join(PROJECT_ROOT, "**", "Mcts_*.py"), recursive=True)
    strategies = [f for f in all_py_files if os.path.basename(f) in valid_strategies]
    target_tfs = ['10m', '15m', '30m', '60m']
    
    analysis_results = []
    
    for tf in target_tfs:
        tf_strats = [s for s in strategies if s.endswith(f"_{tf}.py")]
        if not tf_strats: continue
        
        print(f"Processing {tf} - {len(tf_strats)} strategies...")
        df_hist = load_data(tf)
        n_components = 2 if tf in ['30m', '60m'] else 3
        
        # Suppress warnings from hmmlearn
        import warnings
        warnings.filterwarnings("ignore")
        
        hmm, df_clean = fit_hmm_model(df_hist, n_components=n_components)
        
        # Identify Normal and Panic states based on Volatility
        state_vols = df_clean.groupby('State')['Vol_20'].mean()
        state_normal = state_vols.idxmin()
        state_panic = state_vols.idxmax()
        
        print(f"  TF={tf}: State Normal={state_normal}, State Panic={state_panic}")
        
        for strat_path in tf_strats:
            filename = os.path.basename(strat_path)
            try:
                strat_class = emulator.load_strategy_from_file(strat_path)
                strat = strat_class()
                res = emulator.engine.run(strat, df_hist)
                
                # Align PnL
                pnl = res.equity_curve.diff().fillna(0)
                # Keep only indices present in df_clean
                pnl_aligned = pnl.loc[df_clean.index]
                
                pnl_normal = pnl_aligned[df_clean['State'] == state_normal]
                pnl_panic = pnl_aligned[df_clean['State'] == state_panic]
                
                def calc_state_sharpe(state_pnl):
                    if len(state_pnl) < 2 or state_pnl.std() == 0: return 0
                    return state_pnl.mean() / state_pnl.std()
                    
                sharpe_normal = calc_state_sharpe(pnl_normal) * np.sqrt(252 * 5) # Scale pseudo-annualized
                sharpe_panic = calc_state_sharpe(pnl_panic) * np.sqrt(252 * 5)
                
                mean_pnl_norm = pnl_normal.mean()
                mean_pnl_panic = pnl_panic.mean()
                
                # Classify
                if sharpe_normal > 0.5 and sharpe_panic < 0:
                    classification = "Normal/Trend Specialist"
                elif sharpe_panic > 0.5 and sharpe_normal < 0:
                    classification = "Panic/Reversion Specialist"
                elif sharpe_normal > 0.2 and sharpe_panic > 0.2:
                    classification = "All-Weather"
                elif sharpe_normal < 0 and sharpe_panic < 0:
                    classification = "Garbage/Overfit"
                else:
                    classification = "Mixed/Weak"
                    
                analysis_results.append({
                    'Strategy': filename,
                    'Timeframe': tf,
                    'Sharpe_Normal': round(sharpe_normal, 3),
                    'Sharpe_Panic': round(sharpe_panic, 3),
                    'Classification': classification
                })
            except Exception as e:
                print(f"Error on {filename}: {e}")
                
    df_results = pd.DataFrame(analysis_results)
    
    # Merge with passed status from previous run to see correlation
    val_csv = os.path.join(PROJECT_ROOT, "regime_tagging_research", "all_alphas_validation_results.csv")
    if os.path.exists(val_csv):
        val_df = pd.read_csv(val_csv)
        df_results = pd.merge(df_results, val_df[['Strategy', 'Passed']], on='Strategy', how='left')
    
    output_path = os.path.join(PROJECT_ROOT, "regime_tagging_research", "regime_conditional_classification.csv")
    df_results.to_csv(output_path, index=False)
    
    print("\n--- CLASSIFICATION SUMMARY ---")
    print(df_results['Classification'].value_counts())
    
    # Show stats on how classified alphas passed the validation
    if 'Passed' in df_results.columns:
        print("\n--- PASS RATE BY CLASSIFICATION ---")
        for cls in df_results['Classification'].unique():
            subset = df_results[df_results['Classification'] == cls]
            pass_count = subset['Passed'].sum()
            print(f"{cls}: {pass_count}/{len(subset)} ({(pass_count/len(subset)*100) if len(subset)>0 else 0:.1f}%) passed validation.")
    
    print("\nResults saved to", output_path)

if __name__ == '__main__':
    main()
