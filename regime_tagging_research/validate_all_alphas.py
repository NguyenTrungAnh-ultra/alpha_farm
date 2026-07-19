import os
import sys
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core_engine.BacktestEngine import load_data
from core_engine.PlatformEmulator import XNOPlatformEmulator
from regime_tagging_research.run_hmm_monte_carlo_validation import (
    fit_hmm_model,
    stress_transition_matrix,
    generate_synthetic_ohlcv,
    calculate_metrics_for_result
)

def evaluate_single_strategy(
    filepath: str,
    emulator: XNOPlatformEmulator,
    hist_df: pd.DataFrame,
    normal_paths: list,
    stressed_paths: list
) -> dict:
    """Runs baseline and MC validations for a single strategy file."""
    filename = os.path.basename(filepath)
    
    try:
        strategy_class = emulator.load_strategy_from_file(filepath)
    except Exception as e:
        return {'Error': f"Load failed: {e}"}
        
    # 1. Historical Baseline
    try:
        strategy_hist = strategy_class()
        hist_res = emulator.engine.run(strategy_hist, hist_df)
        hist_sharpe, hist_cagr, hist_dd = calculate_metrics_for_result(hist_res)
    except Exception as e:
        return {'Error': f"Hist backtest failed: {e}"}
        
    # 2. Normal MC simulations
    norm_sharpes = []
    norm_dds = []
    for sim_df in normal_paths:
        try:
            strategy_mc = strategy_class()
            res = emulator.engine.run(strategy_mc, sim_df)
            sh, ca, dd = calculate_metrics_for_result(res)
            norm_sharpes.append(sh)
            norm_dds.append(dd)
        except Exception:
            norm_sharpes.append(0.0)
            norm_dds.append(-100.0)
            
    norm_sharpes = np.array(norm_sharpes)
    norm_dds = np.array(norm_dds)
    
    mc_sharpe_mean = np.mean(norm_sharpes)
    mc_dd_mean = np.mean(norm_dds)
    hist_percentile = np.mean(norm_sharpes < hist_sharpe) * 100
    
    # 3. Stressed MC simulations
    stressed_sharpes = []
    for sim_df in stressed_paths:
        try:
            strategy_mc = strategy_class()
            res = emulator.engine.run(strategy_mc, sim_df)
            sh, ca, dd = calculate_metrics_for_result(res)
            stressed_sharpes.append(sh)
        except Exception:
            stressed_sharpes.append(0.0)
            
    stressed_sharpes = np.array(stressed_sharpes)
    mc_sharpe_stressed_mean = np.mean(stressed_sharpes)
    
    # Apply Filtering Rules
    rule1 = hist_percentile <= 85.0
    rule2 = mc_sharpe_mean >= 0.5 * hist_sharpe
    rule3 = mc_sharpe_stressed_mean >= mc_sharpe_mean
    rule4 = mc_sharpe_mean >= 0.3 # Minimum Edge Threshold
    
    passed = (rule1 and rule2) or (rule3 and rule4)
    
    return {
        'Strategy': filename,
        'Hist_Sharpe': hist_sharpe,
        'Hist_CAGR': hist_cagr,
        'Hist_DD': hist_dd,
        'MC_Sharpe_Mean': mc_sharpe_mean,
        'MC_DD_Mean': mc_dd_mean,
        'Hist_Percentile': hist_percentile,
        'MC_Sharpe_Stressed_Mean': mc_sharpe_stressed_mean,
        'Rule1_Percentile_Pass': rule1,
        'Rule2_Sharpe_Ratio_Pass': rule2,
        'Rule3_Stress_Resilience_Pass': rule3,
        'Rule4_Min_Edge_Pass': rule4,
        'Passed': passed
    }

def main():
    print("==============================================================")
    print("      RUNNING SYSTEMATIC VALIDATION ON ALL PUSHED ALPHAS       ")
    print("==============================================================")
    
    strat_dir = os.path.join(PROJECT_ROOT, 'results', 'pushed', 'mcts_strategies')
    if not os.path.exists(strat_dir):
        print(f"Error: Strategy directory not found: {strat_dir}")
        return
        
    all_files = os.listdir(strat_dir)
    strat_files = [f for f in all_files if f.endswith('.py')]
    print(f"Total strategy files found: {len(strat_files)}")
    
    # Group by timeframe
    tf_groups = {}
    for f in strat_files:
        tf = f.split('_')[-1].replace('.py', '')
        if tf not in tf_groups:
            tf_groups[tf] = []
        tf_groups[tf].append(os.path.join(strat_dir, f))
        
    print(f"Grouped into {len(tf_groups)} timeframes: {list(tf_groups.keys())}")
    
    sim_mapping = {
        '1m': 50,
        '3m': 100,
        '5m': 100,
        '10m': 150,
        '15m': 200,
        '30m': 250,
        '60m': 300
    }
    block_size = 20
    
    emulator = XNOPlatformEmulator()
    all_results = []
    
    for tf, filepaths in tf_groups.items():
        n_simulations = sim_mapping.get(tf, 100)
        print(f"\n--------------------------------------------------")
        print(f"Processing timeframe {tf} ({len(filepaths)} strategies, n_simulations={n_simulations})")
        print(f"--------------------------------------------------")
        
        # 1. Load historical data
        try:
            hist_df = load_data(timeframe=tf)
            print(f"Loaded {len(hist_df)} historical bars for {tf}")
        except Exception as e:
            print(f"Error loading historical data for {tf}: {e}")
            continue
            
        # 2. Fit HMM model
        # 1m, 3m, 5m, 10m, 15m -> 3 states (to capture extreme events)
        # 30m, 60m -> 2 states
        n_states = 3 if tf in ['1m', '3m', '5m', '10m', '15m'] else 2
        
        try:
            hmm, df_clean = fit_hmm_model(hist_df, n_components=n_states)
            trans_matrix = hmm.transmat_
            
            # Find the bad state (highest return variance)
            covars = np.array([np.diag(cov) for cov in hmm.covars_])
            bad_state = np.argmax(covars[:, 0]) # return variance is the first element
            print(f"HMM fitted. Number of states: {n_states}, Bad state identified: {bad_state}")
            
            # Create stressed transition matrix
            stressed_trans = stress_transition_matrix(trans_matrix, bad_state=bad_state, stress_factor=1.5)
        except Exception as e:
            print(f"HMM fitting failed for {tf}: {e}")
            continue
            
        # 3. Generate Monte Carlo Paths once per timeframe
        print(f"Generating {n_simulations} synthetic paths (normal & stressed)...")
        normal_paths = []
        stressed_paths = []
        n_bars = len(df_clean)
        
        for sim_idx in range(n_simulations):
            sim_df_normal = generate_synthetic_ohlcv(
                df_clean, trans_matrix, n_bars=n_bars, block_size=block_size, random_seed=1000 + sim_idx
            )
            normal_paths.append(sim_df_normal)
            
            sim_df_stressed = generate_synthetic_ohlcv(
                df_clean, stressed_trans, n_bars=n_bars, block_size=block_size, random_seed=2000 + sim_idx
            )
            stressed_paths.append(sim_df_stressed)
            
        # 4. Evaluate each strategy
        for idx, filepath in enumerate(filepaths):
            filename = os.path.basename(filepath)
            print(f"[{idx+1}/{len(filepaths)}] Evaluating {filename}...")
            res = evaluate_single_strategy(filepath, emulator, hist_df, normal_paths, stressed_paths)
            if 'Error' in res:
                print(f"  FAILED: {res['Error']}")
                continue
            
            res['Timeframe'] = tf
            all_results.append(res)
            
            p_str = "YES" if res['Passed'] else "NO"
            print(f"  Result: {p_str} (Sharpe: {res['Hist_Sharpe']:.2f} -> MC: {res['MC_Sharpe_Mean']:.2f}, Stressed: {res['MC_Sharpe_Stressed_Mean']:.2f}, Percentile: {res['Hist_Percentile']:.1f}%)")
            
    # 5. Save results to CSV
    if not all_results:
        print("No successful evaluations.")
        return
        
    df_results = pd.DataFrame(all_results)
    csv_path = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'all_alphas_validation_results.csv')
    df_results.to_csv(csv_path, index=False)
    print(f"\nDetailed CSV saved to {csv_path}")
    
    # 6. Generate Summary Markdown Report
    passed_df = df_results[df_results['Passed'] == True]
    failed_df = df_results[df_results['Passed'] == False]
    
    report_path = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'all_alphas_validation_summary.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Systematic Alpha Validation Report (149 Alphas)\n\n")
        f.write("This report presents the validation of all 149 pushed alphas in `results/pushed/` using the HMM-guided Monte Carlo validation rules.\n\n")
        
        f.write("## Validation Rules Summary\n\n")
        f.write("A strategy is accepted (**YES**) if it satisfies:\n")
        f.write("1. **(Rule 1 AND Rule 2)** OR **Rule 3**\n\n")
        f.write("Where:\n")
        f.write("- **Rule 1 (Overfitting Filter)**: `Historical Sharpe Percentile <= 85%` (The historical backtest must not be an extreme outlier/lucky path).\n")
        f.write("- **Rule 2 (Edge Retainment)**: `MC Sharpe mean (Normal) >= 0.5 * Historical Sharpe` (The strategy must retain at least 50% of its Sharpe on synthetic paths).\n")
        f.write("- **Rule 3 (Stress Resilience Bonus)**: `MC Sharpe mean (Stressed) >= MC Sharpe mean (Normal)` (The strategy structurally benefits from or remains stable under increased volatility and crash regimes).\n\n")
        
        f.write("## Executive Metrics\n\n")
        f.write(f"- **Total Evaluated Alphas**: {len(df_results)}\n")
        f.write(f"- **Passed (YES)**: {len(passed_df)} ({len(passed_df)/len(df_results)*100:.1f}%)\n")
        f.write(f"- **Failed (NO)**: {len(failed_df)} ({len(failed_df)/len(df_results)*100:.1f}%)\n\n")
        
        # Summary by Timeframe
        f.write("### Pass Rate by Timeframe\n\n")
        f.write("| Timeframe | Evaluated | Passed (YES) | Failed (NO) | Pass Rate (%) |\n")
        f.write("|---|---|---|---|---|\n")
        for tf in sorted(df_results['Timeframe'].unique()):
            tf_df = df_results[df_results['Timeframe'] == tf]
            p = len(tf_df[tf_df['Passed'] == True])
            f.write(f"| {tf} | {len(tf_df)} | {p} | {len(tf_df) - p} | {p/len(tf_df)*100:.1f}% |\n")
            
        f.write("\n## Passed Alphas (YES)\n\n")
        f.write("| Strategy | TF | Hist Sharpe | MC Sharpe | Stressed Sharpe | Hist Percentile | Reason |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for _, row in passed_df.sort_values(by=['Timeframe', 'Hist_Sharpe'], ascending=[True, False]).iterrows():
            reason = []
            if row['Rule1_Percentile_Pass'] and row['Rule2_Sharpe_Ratio_Pass']:
                reason.append("Robust (Rule 1 & 2)")
            if row['Rule3_Stress_Resilience_Pass']:
                reason.append("Stress Resilient (Rule 3)")
            f.write(f"| {row['Strategy']} | {row['Timeframe']} | {row['Hist_Sharpe']:.2f} | {row['MC_Sharpe_Mean']:.2f} | {row['MC_Sharpe_Stressed_Mean']:.2f} | {row['Hist_Percentile']:.1f}% | {' + '.join(reason)} |\n")
            
        f.write("\n## Sample Failed Alphas (NO - Top 20 by Hist Sharpe)\n\n")
        f.write("| Strategy | TF | Hist Sharpe | MC Sharpe | Stressed Sharpe | Hist Percentile | Failed Rules |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for _, row in failed_df.sort_values(by='Hist_Sharpe', ascending=False).head(20).iterrows():
            failed_rules = []
            if not (row['Rule1_Percentile_Pass'] and row['Rule2_Sharpe_Ratio_Pass']):
                failed_rules.append("Rule 1&2 (Overfit/Edge Loss)")
            if not row['Rule3_Stress_Resilience_Pass']:
                failed_rules.append("Rule 3 (Stress Vulnerability)")
            f.write(f"| {row['Strategy']} | {row['Timeframe']} | {row['Hist_Sharpe']:.2f} | {row['MC_Sharpe_Mean']:.2f} | {row['MC_Sharpe_Stressed_Mean']:.2f} | {row['Hist_Percentile']:.1f}% | {', '.join(failed_rules)} |\n")
            
    print(f"Summary report written to {report_path}")

if __name__ == "__main__":
    main()
