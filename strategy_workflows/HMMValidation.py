import os
import sys
import numpy as np
import pandas as pd
import joblib
from hmmlearn.hmm import GaussianHMM

from utilities.AppConfig import (
    PROJECT_ROOT, 
    HMM_COMPONENTS, 
    HMM_STRESS_FACTOR, 
    HMM_BLOCK_SIZE, 
    HMM_PATHS_PER_TF,
    HMM_RULE_PERCENTILE,
    HMM_RULE_SHARPE_RATIO,
    HMM_RULE_MIN_EDGE
)
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
    
    # Calculate state means to determine the bad_state dynamically
    state_stats = []
    for s in range(n_components):
        state_data = df_clean[df_clean['State'] == s]
        if len(state_data) > 0:
            mean_vol = state_data['Vol_20'].mean()
            mean_ret = state_data['Log_Ret'].mean()
            state_stats.append({'state': s, 'mean_vol': mean_vol, 'mean_ret': mean_ret})
    
    # The bad state is the one with the highest volatility (and usually negative return)
    if state_stats:
        state_stats.sort(key=lambda x: x['mean_vol'], reverse=True)
        bad_state = state_stats[0]['state']
    else:
        bad_state = 1
        
    return hmm, df_clean, bad_state

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
    
    blocks_library = {}
    for state in range(n_states):
        indices = np.where(df_clean['State'].values[:-block_size] == state)[0]
        blocks_library[state] = indices

    n_blocks = n_bars // block_size
    state_sequence = []
    
    current_state = 0
    state_sequence.append(current_state)
    
    for _ in range(n_blocks - 1):
        probs = trans_matrix[current_state]
        current_state = np.random.choice(n_states, p=probs)
        state_sequence.append(current_state)
        
    sim_open_ratio, sim_high_ratio, sim_low_ratio, sim_close_ratio, sim_volume = [], [], [], [], []
    
    close_raw = df_clean['Close'].values
    open_raw = df_clean['Open'].values
    high_raw = df_clean['High'].values
    low_raw = df_clean['Low'].values
    vol_raw = df_clean['Volume'].values
    
    for state in state_sequence:
        start_indices = blocks_library.get(state, [])
        if len(start_indices) == 0:
            start_indices = np.arange(len(df_clean) - block_size)
            
        start_idx = np.random.choice(start_indices)
        
        for offset in range(block_size):
            h_idx = start_idx + offset
            h_prev = h_idx - 1 if h_idx > 0 else 0
            
            prev_close = close_raw[h_prev]
            sim_open_ratio.append(open_raw[h_idx] / prev_close)
            sim_high_ratio.append(high_raw[h_idx] / prev_close)
            sim_low_ratio.append(low_raw[h_idx] / prev_close)
            sim_close_ratio.append(close_raw[h_idx] / prev_close)
            sim_volume.append(vol_raw[h_idx])
            
    n_sim_bars = len(sim_close_ratio)
    sim_close, sim_open, sim_high, sim_low = np.zeros(n_sim_bars), np.zeros(n_sim_bars), np.zeros(n_sim_bars), np.zeros(n_sim_bars)
    
    current_close = initial_price
    for i in range(n_sim_bars):
        sim_open[i] = current_close * sim_open_ratio[i]
        sim_close[i] = current_close * sim_close_ratio[i]
        sim_high[i] = current_close * sim_high_ratio[i]
        sim_low[i] = current_close * sim_low_ratio[i]
        current_close = sim_close[i]
        
    # Create arbitrary dates to appease the backtester
    dates = pd.date_range(start='2020-01-01', periods=n_sim_bars, freq='15min') 
    
    sim_df = pd.DataFrame({
        'Open': sim_open,
        'High': sim_high,
        'Low': sim_low,
        'Close': sim_close,
        'Volume': sim_volume
    }, index=dates)
    sim_df.index.name = 'Datetime'
    
    return sim_df

def precompute_hmm_synthetic_data(timeframes: list, force_retrain: bool = False) -> dict:
    """
    Fits HMM for all timeframes, generates synthetic paths, and caches them.
    Returns: dict mapping tf to {'normal': [paths], 'stressed': [paths]}
    """
    cache_dir = os.path.join(PROJECT_ROOT, "results", "hmm_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, "synthetic_data.pkl")
    
    if not force_retrain and os.path.exists(cache_path):
        print("[HMM Validation] Loading precomputed synthetic data from cache...")
        return joblib.load(cache_path)
        
    print(f"[HMM Validation] Precomputing synthetic paths for {len(timeframes)} timeframes. This may take 1-2 phút...")
    
    synthetic_data = {}
    
    for tf in timeframes:
        try:
            print(f"  -> Fitting HMM for {tf}...")
            hist_df = load_data(tf)
            if len(hist_df) < HMM_BLOCK_SIZE:
                continue
                
            hmm, df_clean, bad_state = fit_hmm_model(hist_df, n_components=HMM_COMPONENTS)
            trans_matrix = hmm.transmat_
            stressed_trans = stress_transition_matrix(trans_matrix, bad_state=bad_state, stress_factor=HMM_STRESS_FACTOR)
            
            n_bars = len(df_clean)
            normal_paths = []
            stressed_paths = []
            
            print(f"  -> Generating {HMM_PATHS_PER_TF} Normal and {HMM_PATHS_PER_TF} Stressed paths for {tf}...")
            for i in range(HMM_PATHS_PER_TF):
                normal_paths.append(generate_synthetic_ohlcv(df_clean, trans_matrix, n_bars, HMM_BLOCK_SIZE, random_seed=1000 + i))
                stressed_paths.append(generate_synthetic_ohlcv(df_clean, stressed_trans, n_bars, HMM_BLOCK_SIZE, random_seed=2000 + i))
                
            synthetic_data[tf] = {
                'normal': normal_paths,
                'stressed': stressed_paths
            }
        except Exception as e:
            print(f"[HMM Validation] Failed to precompute paths for {tf}: {e}")
            import traceback
            traceback.print_exc()
            
    print(f"[HMM Validation] Saving synthetic paths to cache: {cache_path}")
    joblib.dump(synthetic_data, cache_path)
    return synthetic_data

def calculate_metrics_for_result(result):
    """Calculates Sharpe Ratio, CAGR and Max Drawdown from BacktestResult."""
    equity = result.equity_curve
    if len(equity) < 2:
        return 0.0, 0.0, 0.0
        
    total_bars = len(equity)
    # Estimate years from bar count fallback
    years = total_bars / 4800.0 if total_bars > 10000 else total_bars / 1200.0
        
    final_val = equity.iloc[-1]
    initial_val = equity.iloc[0]
    
    if final_val > 0 and initial_val > 0:
        cagr = (final_val / initial_val) ** (1.0 / max(years, 0.1)) - 1.0
    else:
        cagr = -1.0
        
    returns = equity.pct_change().dropna()
    if returns.std() > 0:
        annual_bars = 4800 if total_bars > 10000 else 1200
        sharpe = (returns.mean() / returns.std()) * np.sqrt(annual_bars)
    else:
        sharpe = 0.0
        
    cum_max = equity.cummax()
    drawdown = (equity - cum_max) / cum_max * 100
    max_dd = drawdown.min()
    
    return sharpe, cagr, max_dd

def validate_strategy_with_hmm(strategy, normal_paths: list, stressed_paths: list, hist_sharpe: float) -> tuple[bool, str]:
    """
    Validates a compiled strategy using the precomputed synthetic paths.
    Returns: (passed: bool, reason: str)
    """
    emulator = XNOPlatformEmulator()
    
    norm_sharpes = []
    for sim_df in normal_paths:
        try:
            res = emulator.engine.run(strategy, sim_df)
            sh, ca, dd = calculate_metrics_for_result(res)
            norm_sharpes.append(sh)
        except Exception:
            norm_sharpes.append(0.0)
            
    stressed_sharpes = []
    for sim_df in stressed_paths:
        try:
            res = emulator.engine.run(strategy, sim_df)
            sh, ca, dd = calculate_metrics_for_result(res)
            stressed_sharpes.append(sh)
        except Exception:
            stressed_sharpes.append(0.0)
            
    norm_sharpes = np.array(norm_sharpes)
    stressed_sharpes = np.array(stressed_sharpes)
    
    mc_sharpe_mean = np.mean(norm_sharpes)
    mc_sharpe_stressed_mean = np.mean(stressed_sharpes)
    hist_percentile = np.mean(norm_sharpes < hist_sharpe) * 100
    
    # Nhóm A: Chiến lược Trend-following / Mean Reversion chuẩn
    # Bắt buộc không overfit lịch sử và giữ được phong độ tối thiểu (vá lỗi toán học số âm)
    rule1 = hist_percentile <= HMM_RULE_PERCENTILE
    rule2 = mc_sharpe_mean >= max(HMM_RULE_SHARPE_RATIO * hist_sharpe, HMM_RULE_MIN_EDGE)
    
    # Nhóm B: Chiến lược Đầu cơ Khủng hoảng (Crisis Alpha / Long Volatility)
    # Bắt buộc Stressed Sharpe phải bùng nổ (cao hơn bình thường 0.3) và đạt tối thiểu 0.5.
    # Đổi lại, cho phép Sharpe bình thường được phép âm nhẹ (tối thiểu -0.2)
    rule3 = mc_sharpe_stressed_mean >= max(mc_sharpe_mean + 0.3, 0.5)
    rule4 = mc_sharpe_mean >= -0.2
    
    passed = (rule1 and rule2) or (rule3 and rule4)
    
    if passed:
        reason = f"Passed HMM Filter: MC Sharpe={mc_sharpe_mean:.2f}, Stressed={mc_sharpe_stressed_mean:.2f}, %ile={hist_percentile:.1f}%"
    else:
        reason = f"Failed HMM Filter: MC Sharpe={mc_sharpe_mean:.2f}, Stressed={mc_sharpe_stressed_mean:.2f}, %ile={hist_percentile:.1f}%"
        
    return passed, reason
