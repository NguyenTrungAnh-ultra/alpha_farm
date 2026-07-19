import os
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    csv_path = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'all_alphas_validation_results.csv')
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}")
        return
        
    df = pd.read_csv(csv_path)
    
    # Define rules
    r1 = df['Hist_Percentile'] <= 85.0
    r2 = df['MC_Sharpe_Mean'] >= 0.5 * df['Hist_Sharpe']
    r3 = df['MC_Sharpe_Stressed_Mean'] >= df['MC_Sharpe_Mean']
    r4 = df['MC_Sharpe_Mean'] >= 0.3
    
    # Calculate different Rule Sets
    # Rule Set 1: Strict 2-Tier Rule (Rule 1 & Rule 2)
    df['RuleSet_1'] = r1 & r2
    
    # Rule Set 2: Original Combo (Rule 1 & Rule 2) OR Rule 3
    df['RuleSet_2'] = (r1 & r2) | r3
    
    # Rule Set 3: Updated Combo (Rule 1 & Rule 2) OR (Rule 3 & Rule 4)
    df['RuleSet_3'] = (r1 & r2) | (r3 & r4)
    
    # Print Comparison Table
    print("==========================================================================================")
    print("                      COMPARATIVE ANALYSIS OF VALIDATION RULE SETS                        ")
    print("==========================================================================================")
    header = f"{'TF':<6} | {'Total':<5} | {'RuleSet 1 (R1 & R2)':<22} | {'RuleSet 2 (Combo, no R4)':<24} | {'RuleSet 3 (Combo with R4)':<25}"
    print(header)
    print("-" * len(header))
    
    tfs = sorted(df['Timeframe'].unique(), key=lambda x: int(x.replace('m', '')) if 'm' in x else 0)
    # Sort timeframes properly: 1m, 3m, 5m, 10m, 15m, 30m, 60m
    tf_order = ['1m', '3m', '5m', '10m', '15m', '30m', '60m']
    
    for tf in tf_order:
        if tf not in df['Timeframe'].values:
            continue
        tf_df = df[df['Timeframe'] == tf]
        tot = len(tf_df)
        p1 = len(tf_df[tf_df['RuleSet_1'] == True])
        p2 = len(tf_df[tf_df['RuleSet_2'] == True])
        p3 = len(tf_df[tf_df['RuleSet_3'] == True])
        
        r1_str = f"{p1} ({p1/tot*100:.1f}%)"
        r2_str = f"{p2} ({p2/tot*100:.1f}%)"
        r3_str = f"{p3} ({p3/tot*100:.1f}%)"
        
        print(f"{tf:<6} | {tot:<5} | {r1_str:<22} | {r2_str:<24} | {r3_str:<25}")
    print("==========================================================================================")
    
    # Global summary
    tot_global = len(df)
    g1 = len(df[df['RuleSet_1'] == True])
    g2 = len(df[df['RuleSet_2'] == True])
    g3 = len(df[df['RuleSet_3'] == True])
    print(f"{'Global':<6} | {tot_global:<5} | {f'{g1} ({g1/tot_global*100:.1f}%)':<22} | {f'{g2} ({g2/tot_global*100:.1f}%)':<24} | {f'{g3} ({g3/tot_global*100:.1f}%)':<25}")
    print("==========================================================================================")

if __name__ == "__main__":
    main()
