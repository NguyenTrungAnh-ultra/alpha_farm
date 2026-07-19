import os
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    csv_path = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'all_alphas_validation_results.csv')
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}")
        return
        
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} records from {csv_path}")
    
    # Recalculate rules
    # Rule 1: Percentile <= 85.0
    # Rule 2: MC Sharpe Mean >= 0.5 * Hist Sharpe
    # Rule 3: MC Sharpe Stressed Mean >= MC Sharpe Mean
    # Rule 4: MC Sharpe Mean >= 0.3 (Minimum viable edge threshold)
    df['Rule1_Percentile_Pass'] = df['Hist_Percentile'] <= 85.0
    df['Rule2_Sharpe_Ratio_Pass'] = df['MC_Sharpe_Mean'] >= 0.5 * df['Hist_Sharpe']
    df['Rule3_Stress_Resilience_Pass'] = df['MC_Sharpe_Stressed_Mean'] >= df['MC_Sharpe_Mean']
    df['Rule4_Min_Edge_Pass'] = df['MC_Sharpe_Mean'] >= 0.3
    
    # New Passed logic: (Rule 1 & 2) OR (Rule 3 & 4)
    df['Passed'] = (df['Rule1_Percentile_Pass'] & df['Rule2_Sharpe_Ratio_Pass']) | \
                   (df['Rule3_Stress_Resilience_Pass'] & df['Rule4_Min_Edge_Pass'])
                   
    # Save back to CSV
    df.to_csv(csv_path, index=False)
    print(f"Updated CSV written back to {csv_path}")
    
    # Generate Summary Markdown Report
    passed_df = df[df['Passed'] == True]
    failed_df = df[df['Passed'] == False]
    
    report_path = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'all_alphas_validation_summary.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Systematic Alpha Validation Report (149 Alphas)\n\n")
        f.write("This report presents the validation of all 149 pushed alphas in `results/pushed/` using the HMM-guided Monte Carlo validation rules.\n\n")
        
        f.write("## Validation Rules Summary\n\n")
        f.write("A strategy is accepted (**YES**) if it satisfies:\n")
        f.write("1. **(Rule 1 AND Rule 2)** OR **(Rule 3 AND Rule 4)**\n\n")
        f.write("Where:\n")
        f.write("- **Rule 1 (Overfitting Filter)**: `Historical Sharpe Percentile <= 85%` (The historical backtest must not be an extreme outlier/lucky path).\n")
        f.write("- **Rule 2 (Edge Retainment)**: `MC Sharpe mean (Normal) >= 0.5 * Historical Sharpe` (The strategy must retain at least 50% of its Sharpe on synthetic paths).\n")
        f.write("- **Rule 3 (Stress Resilience Bonus)**: `MC Sharpe mean (Stressed) >= MC Sharpe mean (Normal)` (The strategy structurally benefits from or remains stable under increased volatility and crash regimes).\n")
        f.write("- **Rule 4 (Minimum Edge Threshold)**: `MC Sharpe mean (Normal) >= 0.3` (The strategy must demonstrate a minimum viable performance in the simulated world. This filters out overfitted near-zero noise strategies passing Rule 3 by chance).\n\n")
        
        f.write("## Executive Metrics\n\n")
        f.write(f"- **Total Evaluated Alphas**: {len(df)}\n")
        f.write(f"- **Passed (YES)**: {len(passed_df)} ({len(passed_df)/len(df)*100:.1f}%)\n")
        f.write(f"- **Failed (NO)**: {len(failed_df)} ({len(failed_df)/len(df)*100:.1f}%)\n\n")
        
        # Summary by Timeframe
        f.write("### Pass Rate by Timeframe\n\n")
        f.write("| Timeframe | Evaluated | Passed (YES) | Failed (NO) | Pass Rate (%) |\n")
        f.write("|---|---|---|---|---|\n")
        for tf in sorted(df['Timeframe'].unique()):
            tf_df = df[df['Timeframe'] == tf]
            p = len(tf_df[tf_df['Passed'] == True])
            f.write(f"| {tf} | {len(tf_df)} | {p} | {len(tf_df) - p} | {p/len(tf_df)*100:.1f}% |\n")
            
        f.write("\n## Passed Alphas (YES)\n\n")
        f.write("| Strategy | TF | Hist Sharpe | MC Sharpe | Stressed Sharpe | Hist Percentile | Reason |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for _, row in passed_df.sort_values(by=['Timeframe', 'Hist_Sharpe'], ascending=[True, False]).iterrows():
            reason = []
            if row['Rule1_Percentile_Pass'] and row['Rule2_Sharpe_Ratio_Pass']:
                reason.append("Robust (Rule 1 & 2)")
            if row['Rule3_Stress_Resilience_Pass'] and row['Rule4_Min_Edge_Pass']:
                reason.append("Stress Resilient (Rule 3 & 4)")
            f.write(f"| {row['Strategy']} | {row['Timeframe']} | {row['Hist_Sharpe']:.2f} | {row['MC_Sharpe_Mean']:.2f} | {row['MC_Sharpe_Stressed_Mean']:.2f} | {row['Hist_Percentile']:.1f}% | {' + '.join(reason)} |\n")
            
        f.write("\n## Sample Failed Alphas (NO - Top 20 by Hist Sharpe)\n\n")
        f.write("| Strategy | TF | Hist Sharpe | MC Sharpe | Stressed Sharpe | Hist Percentile | Failed Rules |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for _, row in failed_df.sort_values(by='Hist_Sharpe', ascending=False).head(20).iterrows():
            failed_rules = []
            if not (row['Rule1_Percentile_Pass'] and row['Rule2_Sharpe_Ratio_Pass']):
                failed_rules.append("Rule 1&2 (Overfit/Edge Loss)")
            if not (row['Rule3_Stress_Resilience_Pass'] and row['Rule4_Min_Edge_Pass']):
                failed_rules.append("Rule 3&4 (Stress Vulnerability/No Edge)")
            f.write(f"| {row['Strategy']} | {row['Timeframe']} | {row['Hist_Sharpe']:.2f} | {row['MC_Sharpe_Mean']:.2f} | {row['MC_Sharpe_Stressed_Mean']:.2f} | {row['Hist_Percentile']:.1f}% | {', '.join(failed_rules)} |\n")
            
    print(f"Summary report written to {report_path}")

if __name__ == "__main__":
    main()
