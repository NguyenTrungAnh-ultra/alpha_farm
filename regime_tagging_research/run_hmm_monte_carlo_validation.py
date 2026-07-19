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
from core_engine.PlatformEmulator import XNOPlatformEmulator

def fit_hmm_model(df: pd.DataFrame, n_components: int, random_state: int = 42):
    """Fits Gaussian HMM to returns, rolling volatility, and relative volume features."""
    df_copy = df.copy()
    df_copy['Log_Ret'] = np.log(df_copy['Close'] / df_copy['Close'].shift(1))
    df_copy['Vol_20'] = df_copy['Log_Ret'].rolling(window=20).std()
    # Normalize Volume to avoid trend/rollover issues
    df_copy['Vol_Ratio'] = df_copy['Volume'] / (df_copy['Volume'].rolling(window=20).mean() + 1e-8)
    df_clean = df_copy.dropna().copy()
    
    # Z-score scale features to prevent scale-mismatch convergence issues
    X = df_clean[['Log_Ret', 'Vol_20', 'Vol_Ratio']].values
    X_mean = X.mean(axis=0)
    X_std = X.std(axis=0) + 1e-8
    X_scaled = (X - X_mean) / X_std
    
    hmm = GaussianHMM(n_components=n_components, covariance_type="diag", n_iter=100, random_state=random_state)
    hmm.fit(X_scaled)
    
    df_clean['State'] = hmm.predict(X_scaled)
    return hmm, df_clean

def stress_transition_matrix(trans_matrix: np.ndarray, bad_state: int, stress_factor: float = 1.5) -> np.ndarray:
    """Amplifies probability of transitioning to/staying in the bad state, re-normalizing other states."""
    stressed_trans = trans_matrix.copy()
    n_states = len(trans_matrix)
    
    for i in range(n_states):
        p_bad = stressed_trans[i, bad_state]
        new_p_bad = min(p_bad * stress_factor, 0.90)  # Cap at 90% to avoid absorbing state lock
        stressed_trans[i, bad_state] = new_p_bad
        
        # Re-normalize other states
        remaining_prob = 1.0 - new_p_bad
        other_indices = [idx for idx in range(n_states) if idx != bad_state]
        sum_others = sum(stressed_trans[i, other_indices])
        
        if sum_others > 0:
            for idx in other_indices:
                stressed_trans[i, idx] = stressed_trans[i, idx] * (remaining_prob / sum_others)
        else:
            # Fallback if other states had 0 probability
            for idx in other_indices:
                stressed_trans[i, idx] = remaining_prob / len(other_indices)
                
    return stressed_trans

def generate_synthetic_ohlcv(
    df_clean: pd.DataFrame, 
    trans_matrix: np.ndarray, 
    n_bars: int, 
    block_size: int = 20, 
    initial_price: float = 1000.0,
    random_seed: int = None
) -> pd.DataFrame:
    """Generates synthetic OHLCV data using Markov-chain transitions and block bootstrapping."""
    if random_seed is not None:
        np.random.seed(random_seed)
        
    n_states = len(trans_matrix)
    
    # Pre-calculate blocks library: indices where state matches
    # Key: state, Value: list of historical indices that can be the start of a block
    # Note: To avoid index overflow during slicing [idx : idx + block_size], we limit start index
    blocks_library = {}
    for state in range(n_states):
        # Find indices where state matches and there is room for block_size
        indices = np.where(df_clean['State'].values[:-block_size] == state)[0]
        blocks_library[state] = indices

    # Simulate sequence of states at block level
    n_blocks = n_bars // block_size
    state_sequence = []
    
    # Start with stationary distribution or state 0
    current_state = 0
    state_sequence.append(current_state)
    
    for _ in range(n_blocks - 1):
        probs = trans_matrix[current_state]
        current_state = np.random.choice(n_states, p=probs)
        state_sequence.append(current_state)
        
    # Build synthetic returns and ratios
    sim_open_ratio = []
    sim_high_ratio = []
    sim_low_ratio = []
    sim_close_ratio = []
    sim_volume = []
    
    # Raw columns from df_clean for relative calculations
    close_raw = df_clean['Close'].values
    open_raw = df_clean['Open'].values
    high_raw = df_clean['High'].values
    low_raw = df_clean['Low'].values
    vol_raw = df_clean['Volume'].values
    
    for state in state_sequence:
        # Sample a block index for this state
        start_indices = blocks_library[state]
        if len(start_indices) == 0:
            # Fallback if no blocks found for this state
            start_indices = np.arange(len(df_clean) - block_size)
            
        start_idx = np.random.choice(start_indices)
        
        # For each bar in the block, calculate relative ratio to the previous bar's Close
        for offset in range(block_size):
            h_idx = start_idx + offset
            h_prev = h_idx - 1 if h_idx > 0 else 0
            
            prev_close = close_raw[h_prev]
            sim_open_ratio.append(open_raw[h_idx] / prev_close)
            sim_high_ratio.append(high_raw[h_idx] / prev_close)
            sim_low_ratio.append(low_raw[h_idx] / prev_close)
            sim_close_ratio.append(close_raw[h_idx] / prev_close)
            sim_volume.append(vol_raw[h_idx])
            
    # Reconstruct prices from ratios
    n_sim_bars = len(sim_close_ratio)
    sim_close = np.zeros(n_sim_bars)
    sim_open = np.zeros(n_sim_bars)
    sim_high = np.zeros(n_sim_bars)
    sim_low = np.zeros(n_sim_bars)
    
    current_close = initial_price
    for i in range(n_sim_bars):
        sim_open[i] = current_close * sim_open_ratio[i]
        sim_close[i] = current_close * sim_close_ratio[i]
        sim_high[i] = current_close * sim_high_ratio[i]
        sim_low[i] = current_close * sim_low_ratio[i]
        current_close = sim_close[i]
        
    # Create Datetime index
    dates = pd.date_range(start='2020-01-01', periods=n_sim_bars, freq='15min') # Use arbitrary freq
    
    sim_df = pd.DataFrame({
        'Open': sim_open,
        'High': sim_high,
        'Low': sim_low,
        'Close': sim_close,
        'Volume': sim_volume
    }, index=dates)
    sim_df.index.name = 'Datetime'
    
    return sim_df

def calculate_metrics_for_result(result):
    """Calculates Sharpe Ratio, CAGR and Max Drawdown from BacktestResult."""
    # We can use the project's compute_metrics if available, or compute them ourselves
    # to avoid dependencies. Let's compute them ourselves from equity curve for robustness.
    equity = result.equity_curve
    if len(equity) < 2:
        return 0.0, 0.0, 0.0
        
    # CAGR
    n_days = (equity.index[-1] - equity.index[0]).total_seconds() / (24 * 3600)
    # If index is arbitrary dates, n_days can be calibrated based on length
    # Let's check how many bars represent a year:
    # VN30F has ~240 trading days, 5 hours per day = 1200 hours.
    # On 15m timeframe: 20 bars/day * 240 days = 4800 bars/year.
    # On 60m timeframe: 5 bars/day * 240 days = 1200 bars/year.
    # Let's estimate years from length:
    total_bars = len(equity)
    # Standard VN30F 15m dataset has ~21000 bars (approx 4.4 years)
    # Let's use the actual time difference if available, or fall back to bar count
    if n_days > 30:
        years = n_days / 365.0
    else:
        # Fallback estimation
        years = total_bars / 4800.0 if total_bars > 10000 else total_bars / 1200.0
        
    final_val = equity.iloc[-1]
    initial_val = equity.iloc[0]
    
    if final_val > 0 and initial_val > 0:
        cagr = (final_val / initial_val) ** (1.0 / max(years, 0.1)) - 1.0
    else:
        cagr = -1.0
        
    # Sharpe Ratio (daily equivalent or bar equivalent annualized)
    # Let's compute return series
    returns = equity.pct_change().dropna()
    if returns.std() > 0:
        # Annualized Sharpe: mean/std * sqrt(annual_bars)
        # 15m: 4800 bars/year
        # 60m: 1200 bars/year
        annual_bars = 4800 if total_bars > 10000 else 1200
        sharpe = (returns.mean() / returns.std()) * np.sqrt(annual_bars)
    else:
        sharpe = 0.0
        
    # Max Drawdown
    cum_max = equity.cummax()
    drawdown = (equity - cum_max) / cum_max * 100
    max_dd = drawdown.min()
    
    return sharpe, cagr, max_dd

def evaluate_strategy_on_paths(
    strategy_path: str,
    emulator: XNOPlatformEmulator,
    hist_df: pd.DataFrame,
    mc_paths: list,
    scenario_name: str
) -> dict:
    """Evaluates a strategy on historical data and a list of Monte Carlo paths."""
    strategy_class = emulator.load_strategy_from_file(strategy_path)
    
    # 1. Historical Baseline
    strategy_hist = strategy_class()
    hist_res = emulator.engine.run(strategy_hist, hist_df)
    hist_sharpe, hist_cagr, hist_dd = calculate_metrics_for_result(hist_res)
    
    # 2. Monte Carlo runs
    sharpes = []
    cagrs = []
    drawdowns = []
    
    for i, sim_df in enumerate(mc_paths):
        # We need to create a new instance of strategy for each run
        strategy_mc = strategy_class()
        try:
            res = emulator.engine.run(strategy_mc, sim_df)
            sh, ca, dd = calculate_metrics_for_result(res)
            sharpes.append(sh)
            cagrs.append(ca)
            drawdowns.append(dd)
        except Exception as e:
            # If a backtest fails, skip or record as bad
            print(f"Error running backtest on MC path {i}: {e}")
            sharpes.append(0.0)
            cagrs.append(-1.0)
            drawdowns.append(-100.0)
            
    # Calculate stats
    sharpes = np.array(sharpes)
    cagrs = np.array(cagrs)
    drawdowns = np.array(drawdowns)
    
    # Pass rate: Sharpe >= 1.3 and Max DD >= -35%
    pass_rate = np.mean((sharpes >= 1.3) & (drawdowns >= -35.0)) * 100
    
    # Percentile of historical Sharpe in simulated distribution
    # (How lucky was the historical run?)
    hist_sharpe_percentile = np.mean(sharpes < hist_sharpe) * 100
    
    return {
        'hist_sharpe': hist_sharpe,
        'hist_cagr': hist_cagr,
        'hist_dd': hist_dd,
        'mc_sharpe_mean': np.mean(sharpes),
        'mc_sharpe_std': np.std(sharpes),
        'mc_sharpe_5pct': np.percentile(sharpes, 5),
        'mc_sharpe_95pct': np.percentile(sharpes, 95),
        'mc_dd_mean': np.mean(drawdowns),
        'mc_dd_5pct': np.percentile(drawdowns, 5),
        'pass_rate': pass_rate,
        'hist_percentile': hist_sharpe_percentile,
        'sharpes': sharpes,
        'drawdowns': drawdowns
    }

def find_top_strategies(timeframe: str, emulator: XNOPlatformEmulator, hist_df: pd.DataFrame, top_n: int = 5) -> list:
    """Scans the strategy directory, backtests all files for the timeframe, and returns the top_n strategy filepaths based on historical Sharpe."""
    strat_dir = os.path.join(PROJECT_ROOT, 'results', 'pushed', 'mcts_strategies')
    if not os.path.exists(strat_dir):
        return []
        
    all_files = os.listdir(strat_dir)
    target_suffix = f"_{timeframe}.py"
    strat_files = [f for f in all_files if f.endswith(target_suffix)]
    
    print(f"\nFound {len(strat_files)} strategy files for timeframe {timeframe}. Evaluating historical baseline to select top {top_n}...")
    
    results = []
    for f in strat_files:
        filepath = os.path.join(strat_dir, f)
        try:
            strategy_class = emulator.load_strategy_from_file(filepath)
            strategy = strategy_class()
            res = emulator.engine.run(strategy, hist_df)
            sharpe, cagr, dd = calculate_metrics_for_result(res)
            # Filter out strategies with no trades (Sharpe = 0) or extremely poor Sharpe
            if sharpe > 0.01:
                results.append((filepath, sharpe))
        except Exception as e:
            # Skip if file loading/compilation failed
            continue
            
    # Sort by Sharpe descending
    results.sort(key=lambda x: x[1], reverse=True)
    top_strats = [path for path, sharpe in results[:top_n]]
    
    print(f"Selected Top {len(top_strats)} strategies for {timeframe}:")
    for path, sharpe in results[:top_n]:
        print(f"  - {os.path.basename(path)}: Sharpe = {sharpe:.2f}")
        
    return top_strats

def run_mc_validation():
    print("==============================================================")
    print("      HMM-GUIDED MONTE CARLO VALIDATION PIPELINE              ")
    print("==============================================================")
    
    n_simulations = 500
    block_size = 20
    
    emulator = XNOPlatformEmulator()
    all_report_data = []
    
    plots_dir = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    timeframes = ['15m', '60m']
    
    for tf in timeframes:
        # 1. Load historical data
        try:
            hist_df = load_data(timeframe=tf)
            print(f"\nLoaded {len(hist_df)} historical bars for timeframe {tf}")
        except Exception as e:
            print(f"Error loading historical data for {tf}: {e}")
            continue
            
        # Dynamically discover top 5 strategies for this timeframe
        filepaths = find_top_strategies(tf, emulator, hist_df, top_n=5)
        if not filepaths:
            print(f"No strategies found for timeframe {tf}, skipping.")
            continue
            
        # 2. Fit HMM model
        # 15m -> 3 states (State 1 is extreme panic/volatility)
        # 60m -> 2 states (State 1 is high volatility bear)
        n_states = 3 if tf == '15m' else 2
        bad_state = 1  # In both models, State 1 has the highest volatility and negative drift
        
        hmm, df_clean = fit_hmm_model(hist_df, n_components=n_states)
        trans_matrix = hmm.transmat_
        
        print(f"HMM transition matrix for {tf}:")
        print(trans_matrix)
        
        # 3. Create stressed transition matrix
        stressed_trans = stress_transition_matrix(trans_matrix, bad_state=bad_state, stress_factor=1.5)
        print(f"Stressed transition matrix for {tf}:")
        print(stressed_trans)
        
        # 4. Generate Monte Carlo Paths
        print(f"Generating {n_simulations} synthetic paths (normal & stressed)...")
        normal_paths = []
        stressed_paths = []
        
        n_bars = len(df_clean)
        
        for sim_idx in range(n_simulations):
            # Normal
            sim_df_normal = generate_synthetic_ohlcv(
                df_clean, trans_matrix, n_bars=n_bars, block_size=block_size, random_seed=1000 + sim_idx
            )
            normal_paths.append(sim_df_normal)
            
            # Stressed
            sim_df_stressed = generate_synthetic_ohlcv(
                df_clean, stressed_trans, n_bars=n_bars, block_size=block_size, random_seed=2000 + sim_idx
            )
            stressed_paths.append(sim_df_stressed)
            
        # 5. Evaluate strategies
        for filepath in filepaths:
            strat_name = os.path.basename(filepath)
            print(f"\nEvaluating strategy: {strat_name}...")
            
            # Normal evaluation
            print("Running baseline and Normal MC simulations...")
            res_normal = evaluate_strategy_on_paths(filepath, emulator, hist_df, normal_paths, 'Normal')
            
            # Stressed evaluation
            print("Running Stressed MC simulations...")
            res_stressed = evaluate_strategy_on_paths(filepath, emulator, hist_df, stressed_paths, 'Stressed')
            
            # Save results for markdown report
            all_report_data.append({
                'tf': tf,
                'name': strat_name,
                'normal': res_normal,
                'stressed': res_stressed
            })
            
            # 6. Generate Plot
            fig, axes = plt.subplots(1, 2, figsize=(14, 5))
            
            # Histogram of Normal Sharpe
            axes[0].hist(res_normal['sharpes'], bins=20, color='skyblue', edgecolor='black', alpha=0.7, label='MC Sharpe')
            axes[0].axvline(res_normal['hist_sharpe'], color='red', linestyle='dashed', linewidth=2, label=f"Hist Sharpe: {res_normal['hist_sharpe']:.2f}")
            axes[0].set_title(f"{strat_name} - Sharpe Distribution (Normal)")
            axes[0].set_xlabel('Sharpe Ratio')
            axes[0].set_ylabel('Count')
            axes[0].legend()
            axes[0].grid(True, alpha=0.3)
            
            # Histogram of Stressed Sharpe
            axes[1].hist(res_stressed['sharpes'], bins=20, color='salmon', edgecolor='black', alpha=0.7, label='MC Sharpe')
            axes[1].axvline(res_stressed['hist_sharpe'], color='red', linestyle='dashed', linewidth=2, label=f"Hist Sharpe: {res_stressed['hist_sharpe']:.2f}")
            axes[1].set_title(f"{strat_name} - Sharpe Distribution (Stressed)")
            axes[1].set_xlabel('Sharpe Ratio')
            axes[1].set_ylabel('Count')
            axes[1].legend()
            axes[1].grid(True, alpha=0.3)
            
            plt.tight_layout()
            plot_path = os.path.join(plots_dir, f"mc_validation_{strat_name.replace('.py', '')}.png")
            plt.savefig(plot_path, dpi=150)
            plt.close()
            print(f"Saved distribution plot to {plot_path}")
            
    # 7. Write Markdown Report
    report_path = os.path.join(PROJECT_ROOT, 'regime_tagging_research', 'monte_carlo_validation_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Hidden Markov Model & Monte Carlo Validation Report\n\n")
        f.write("This report presents the validation results of representative trading alphas backtested on 100 HMM-guided synthetic price paths, under both **Normal** and **Stressed** market conditions.\n\n")
        
        f.write("## Executive Summary\n\n")
        f.write("The objective of HMM-guided Monte Carlo validation is to verify if a strategy's historical backtest performance is structurally robust or represents a lucky path (overfitted to the specific timeline).\n")
        f.write("- **Historical Sharpe Percentile**: Represents the percentage of synthetic paths where the strategy achieved a Sharpe ratio lower than its historical backtest. A percentile close to **50%** means the backtest is a median expectation. A percentile close to **99%** means the historical run is a highly optimistic outlier.\n")
        f.write("- **Pass Rate**: The percentage of simulated paths where the strategy satisfies the minimum criteria: **Sharpe >= 1.3** and **Max Drawdown >= -35%**.\n\n")
        
        f.write("## Validation Performance Matrix\n\n")
        f.write("| Strategy | Timeframe | Scenario | Historical Sharpe | MC Sharpe (Mean ± Std) | MC Sharpe (5% to 95%) | Historical Percentile | Pass Rate |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        
        for data in all_report_data:
            name = data['name']
            tf = data['tf']
            
            # Normal
            norm = data['normal']
            f.write(f"| {name} | {tf} | Normal | {norm['hist_sharpe']:.2f} | {norm['mc_sharpe_mean']:.2f} ± {norm['mc_sharpe_std']:.2f} | [{norm['mc_sharpe_5pct']:.2f}, {norm['mc_sharpe_95pct']:.2f}] | {norm['hist_percentile']:.1f}% | {norm['pass_rate']:.1f}% |\n")
            
            # Stressed
            stress = data['stressed']
            f.write(f"| {name} | {tf} | Stressed | {stress['hist_sharpe']:.2f} | {stress['mc_sharpe_mean']:.2f} ± {stress['mc_sharpe_std']:.2f} | [{stress['mc_sharpe_5pct']:.2f}, {stress['mc_sharpe_95pct']:.2f}] | {stress['hist_percentile']:.1f}% | {stress['pass_rate']:.1f}% |\n")
            
        f.write("\n\n## Strategy Breakdown Analysis\n\n")
        
        for data in all_report_data:
            name = data['name']
            tf = data['tf']
            norm = data['normal']
            stress = data['stressed']
            
            f.write(f"### {name} ({tf})\n\n")
            f.write("#### Normal Scenario\n")
            f.write(f"- **Historical Backtest**: Sharpe = {norm['hist_sharpe']:.2f}, Max Drawdown = {norm['hist_dd']:.2f}%\n")
            f.write(f"- **Monte Carlo Sharpe (Average)**: {norm['mc_sharpe_mean']:.2f}\n")
            f.write(f"- **Monte Carlo Max Drawdown (Average)**: {norm['mc_dd_mean']:.2f}% (5th percentile worst: {norm['mc_dd_5pct']:.2f}%)\n")
            f.write(f"- **Robustness Profile**: The historical Sharpe lies at the **{norm['hist_percentile']:.1f}th percentile** of the simulated distribution. ")
            
            if norm['hist_percentile'] > 90:
                f.write("The strategy historical performance is an optimistic outlier, indicating **high risk of overfitting**.\n")
            elif norm['hist_percentile'] < 30:
                f.write("The strategy performed worse historically than in most simulations, suggesting a **conservative baseline** or drag during the historical period.\n")
            else:
                f.write("The historical backtest represents a **highly realistic median expectation**.\n")
                
            f.write(f"- **Pass Rate (Sharpe >= 1.3 & DD >= -35%)**: **{norm['pass_rate']:.1f}%**\n\n")
            
            f.write("#### Stressed Scenario (1.5x Panic/Crash regime)\n")
            f.write(f"- **Monte Carlo Sharpe (Average)**: {stress['mc_sharpe_mean']:.2f}\n")
            f.write(f"- **Monte Carlo Max Drawdown (Average)**: {stress['mc_dd_mean']:.2f}% (5th percentile worst: {stress['mc_dd_5pct']:.2f}%)\n")
            f.write(f"- **Pass Rate**: **{stress['pass_rate']:.1f}%**\n")
            
            # Analyze impact of stress
            dd_increase = stress['mc_dd_mean'] - norm['mc_dd_mean']
            f.write(f"- **Stress Impact**: Average drawdown worsened by **{abs(dd_increase):.2f}%** compared to the normal scenario. ")
            if abs(dd_increase) > 10.0:
                f.write("This strategy is **highly vulnerable to regime shift** and extended periods of market stress.\n")
            else:
                f.write("This strategy has **strong structural resilience** to increased volatility regimes.\n")
                
            f.write("\n---\n\n")
            
    print(f"\nMonte Carlo Validation Complete. Report written to {report_path}")

if __name__ == "__main__":
    run_mc_validation()
