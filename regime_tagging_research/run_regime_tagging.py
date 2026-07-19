import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from hmmlearn.hmm import GaussianHMM

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from core_engine.BacktestEngine import load_data

def run_research_for_timeframe(timeframe: str, n_components: int = 3):
    print(f"\n==================================================")
    print(f"Running Regime Tagging Research for {timeframe} with {n_components} states")
    print(f"==================================================")
    
    # 1. Load Data
    try:
        df = load_data(timeframe=timeframe)
        print(f"Loaded {len(df)} rows of data for {timeframe}")
    except Exception as e:
        print(f"Error loading data for {timeframe}: {e}")
        return None
    
    # Ensure sorted by index
    df = df.sort_index()
    
    # 2. Feature Engineering
    # We want features that capture return (direction) and volatility (regime)
    df['Log_Ret'] = np.log(df['Close'] / df['Close'].shift(1))
    
    # Volatility feature: rolling standard deviation of log returns (e.g. over 20 periods)
    df['Vol_20'] = df['Log_Ret'].rolling(window=20).std()
    
    # Additional feature: rolling standard deviation over 100 periods to capture long-term regime
    df['Vol_100'] = df['Log_Ret'].rolling(window=100).std()
    
    # Drop NaNs
    df_clean = df.dropna().copy()
    print(f"Data rows after dropping NaNs: {len(df_clean)}")
    
    # Features for HMM: Log_Ret and Vol_20
    features = ['Log_Ret', 'Vol_20']
    X = df_clean[features].values
    
    # 3. Fit Gaussian HMM
    print("Fitting Gaussian HMM...")
    hmm = GaussianHMM(
        n_components=n_components, 
        covariance_type="diag", 
        n_iter=100, 
        random_state=42
    )
    hmm.fit(X)
    
    # Predict states
    states = hmm.predict(X)
    df_clean['State'] = states
    
    # 4. Analyze Transition Matrix & State Characteristics
    trans_matrix = hmm.transmat_
    means = hmm.means_
    covars = np.array([np.diag(cov) for cov in hmm.covars_])
    
    print("\nTransition Probability Matrix:")
    print(trans_matrix)
    
    print("\nState Means (Log_Ret, Vol_20):")
    print(means)
    
    print("\nState Volatilities (Diag of Covariance):")
    print(covars)
    
    # Evaluate return/volatility characteristics per state in Pandas
    state_stats = []
    for state in range(n_components):
        state_df = df_clean[df_clean['State'] == state]
        pct_occurrence = len(state_df) / len(df_clean) * 100
        
        # Calculate mean and standard deviation of log returns
        mean_ret = state_df['Log_Ret'].mean()
        std_ret = state_df['Log_Ret'].std()
        
        # Win rate if we just go long on every bar
        win_rate = (state_df['Log_Ret'] > 0).mean() * 100
        
        state_stats.append({
            'State': state,
            'Count': len(state_df),
            'Pct': pct_occurrence,
            'Mean_Ret': mean_ret,
            'Std_Ret': std_ret,
            'Win_Rate': win_rate,
            'Mean_Vol_Feature': state_df['Vol_20'].mean()
        })
        
    stats_df = pd.DataFrame(state_stats)
    print("\nState Statistics:")
    print(stats_df.to_string(index=False))
    
    # Save statistics and transition matrix to dict for reporting
    result_summary = {
        'timeframe': timeframe,
        'n_components': n_components,
        'stats': state_stats,
        'trans_matrix': trans_matrix.tolist(),
        'state_means': means.tolist(),
        'state_covars': covars.tolist()
    }
    
    # 5. Visualization
    plots_dir = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    
    # Plot 1: Close Price colored by regime
    axes[0].plot(df_clean.index, df_clean['Close'], color='gray', alpha=0.5, label='Close Price')
    
    # Color segments based on state
    # We can plot scatter or line segments. For high resolution, scatter is easier to visualize.
    colors = ['blue', 'orange', 'green', 'red', 'purple']
    for state in range(n_components):
        state_idx = df_clean['State'] == state
        axes[0].scatter(df_clean.index[state_idx], df_clean['Close'][state_idx], 
                        color=colors[state], s=1, label=f'State {state}')
    axes[0].set_title(f'VN30F Close Price and Tagged Regimes ({timeframe})')
    axes[0].legend(markerscale=10)
    axes[0].grid(True, alpha=0.3)
    
    # Plot 2: Volatility Feature and State
    axes[1].plot(df_clean.index, df_clean['Vol_20'], color='black', alpha=0.7, label='Vol_20 (Rolling Vol)')
    for state in range(n_components):
        state_idx = df_clean['State'] == state
        axes[1].scatter(df_clean.index[state_idx], df_clean['Vol_20'][state_idx], 
                        color=colors[state], s=1, label=f'State {state}')
    axes[1].set_title('Volatility Feature (Vol_20) by State')
    axes[1].legend(markerscale=10)
    axes[1].grid(True, alpha=0.3)
    
    # Plot 3: Cumulative returns of each State vs Buy-and-Hold
    # To see the behavior, let's plot cumulative returns if we hold positions only when in that state
    axes[2].plot(df_clean.index, df_clean['Log_Ret'].cumsum(), color='black', label='Buy & Hold (Cumulative Log Returns)')
    for state in range(n_components):
        # We hold VN30F when in state, else 0 return
        state_ret = np.where(df_clean['State'] == state, df_clean['Log_Ret'], 0.0)
        axes[2].plot(df_clean.index, np.cumsum(state_ret), color=colors[state], label=f'State {state} only')
    axes[2].set_title('Cumulative Returns when holding in specific State')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plot_path = os.path.join(plots_dir, f'regime_plot_{timeframe}_{n_components}states.png')
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"Saved plot to {plot_path}")
    
    return result_summary, df_clean

if __name__ == "__main__":
    timeframes = ['15m', '60m']
    all_results = []
    
    for tf in timeframes:
        # Run with 2 states first
        res2, df2 = run_research_for_timeframe(tf, n_components=2)
        # Run with 3 states
        res3, df3 = run_research_for_timeframe(tf, n_components=3)
        
        if res2:
            all_results.append(res2)
        if res3:
            all_results.append(res3)
            
    # Write a quick summary markdown file
    summary_path = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'regime_tagging_summary.md')
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("# Regime Tagging Feasibility Test Report\n\n")
        f.write("This report summarizes the feasibility test of using Hidden Markov Models (HMM) for tagging market regimes on VN30F futures data.\n\n")
        
        for res in all_results:
            tf = res['timeframe']
            n_states = res['n_components']
            f.write(f"## Timeframe: {tf} | States: {n_states}\n\n")
            
            f.write("### State Statistics\n")
            f.write("| State | Count | Percentage | Mean Log Return | Std Log Return | Win Rate (%) | Mean Volatility Feature |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for st in res['stats']:
                f.write(f"| {st['State']} | {st['Count']} | {st['Pct']:.2f}% | {st['Mean_Ret']:.6f} | {st['Std_Ret']:.6f} | {st['Win_Rate']:.2f}% | {st['Mean_Vol_Feature']:.6f} |\n")
            f.write("\n")
            
            f.write("### Transition Probability Matrix\n")
            f.write("```\n")
            for row in res['trans_matrix']:
                f.write("  " + "  ".join([f"{val:.4f}" for val in row]) + "\n")
            f.write("```\n\n")
            
            f.write("### State Parameter Estimates\n")
            f.write("- **Means (Log Return, Volatility Feature)**:\n")
            for idx, mean in enumerate(res['state_means']):
                f.write(f"  - State {idx}: Return Mean = {mean[0]:.6f}, Vol Mean = {mean[1]:.6f}\n")
            f.write("- **Covariances (Diagonal Elements)**:\n")
            for idx, cov in enumerate(res['state_covars']):
                f.write(f"  - State {idx}: Return Var = {cov[0]:.8f}, Vol Var = {cov[1]:.8f}\n")
            f.write("\n---\n\n")
            
    print(f"\nAnalysis complete. Summary report written to {summary_path}")
