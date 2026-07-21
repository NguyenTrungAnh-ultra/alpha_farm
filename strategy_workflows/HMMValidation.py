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
    MC_CACHE_DIR,
    MARGIN_CALL_DD_THRESHOLD,
    RUIN_RATE_THRESHOLD,
    COST_COVERAGE_MULTIPLIER,
    SAVINGS_RATE_ANNUAL,
    BENCHMARK_BASELINE_PATH
)
import json
from core_engine.BacktestEngine import load_data, AlphaBacktestEngine

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
    }, index=dates).astype('float32')
    sim_df.index.name = 'Datetime'
    
    return sim_df

def precompute_hmm_synthetic_data(timeframes: list, force_retrain: bool = False) -> dict:
    """
    Fits HMM for all timeframes, generates synthetic paths, and caches them.
    Returns: dict mapping tf to {'normal': [paths], 'stressed': [paths]}
    """
    cache_dir = MC_CACHE_DIR
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

def extract_trade_stats_from_result(result) -> dict:
    """Trích xuất thống kê lệnh từ BacktestResult để phục vụ Tầng 2 (Kelly, Cost Coverage)."""
    trades = result.trades
    if not trades:
        return {'win_rate': 0.0, 'avg_win': 0.0, 'avg_loss': 0.0,
                'total_pnl': 0.0, 'total_fees': 0.0, 'n_trades': 0}
    
    pnls = [t.net_pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    n_trades = len(pnls)
    win_rate = len(wins) / n_trades if n_trades > 0 else 0.0
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0
    
    return {
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_pnl': sum(pnls),
        'total_fees': result.total_fees,
        'n_trades': n_trades
    }

def validate_strategy_with_hmm(strategy, normal_paths: list, stressed_paths: list, hist_sharpe: float) -> tuple[bool, int | None, str, dict]:
    """
    Validates a compiled strategy using the 3-Tier Realistic Validation Framework.
    
    Returns:
        passed: bool
        tier_failed: int | None (1, 2, or 3 if failed, None if passed)
        reason: str
        details: dict
    """
    engine = AlphaBacktestEngine()
    
    # -------------------------------------------------------------
    # 1. Thu thập dữ liệu từ Normal Paths
    # -------------------------------------------------------------
    norm_sharpes, norm_cagrs, norm_dds = [], [], []
    all_pnls = []
    total_fees_accum = 0.0
    total_trades_accum = 0
    
    for sim_df in normal_paths:
        try:
            res = engine.run(strategy, sim_df)
            sh, ca, dd = calculate_metrics_for_result(res)
            norm_sharpes.append(sh)
            norm_cagrs.append(ca)
            norm_dds.append(dd)
            
            # Extract trades for Tier 2 aggregated
            stats = extract_trade_stats_from_result(res)
            if stats['n_trades'] > 0:
                all_pnls.extend([t.net_pnl for t in res.trades])
                total_fees_accum += stats['total_fees']
                total_trades_accum += stats['n_trades']
        except Exception:
            norm_sharpes.append(0.0)
            norm_cagrs.append(-1.0)
            norm_dds.append(-100.0)
            
    norm_sharpes = np.array(norm_sharpes)
    norm_cagrs = np.array(norm_cagrs)
    norm_dds = np.array(norm_dds)
    total_paths = len(normal_paths)
    
    mc_cagr_mean = np.mean(norm_cagrs)
    mc_sharpe_mean = np.mean(norm_sharpes)
    
    # -------------------------------------------------------------
    # TẦNG 1: Vật lý - Empirical Risk of Ruin
    # -------------------------------------------------------------
    ruin_count = np.sum(norm_dds <= MARGIN_CALL_DD_THRESHOLD)
    ruin_rate = ruin_count / total_paths if total_paths > 0 else 1.0
    dd_5th = np.percentile(norm_dds, 5) if total_paths > 0 else -100.0
    
    if ruin_rate >= RUIN_RATE_THRESHOLD:
        reason = f"Failed Tier 1: Risk of Ruin {ruin_rate*100:.1f}% >= {RUIN_RATE_THRESHOLD*100:.1f}% (Margin Call Threshold: {MARGIN_CALL_DD_THRESHOLD}%)"
        return False, 1, reason, {'ruin_rate': ruin_rate, 'ruin_count': int(ruin_count), 'total_paths': int(total_paths), 'dd_5th_percentile': float(dd_5th)}
        
    # -------------------------------------------------------------
    # TẦNG 2: Xác suất - Kelly Fraction & Cost Coverage
    # -------------------------------------------------------------
    kelly_fraction = 0.0
    avg_pnl_per_trade = 0.0
    avg_cost_per_trade = 0.0
    cost_coverage = 0.0
    
    if total_trades_accum > 0:
        wins = [p for p in all_pnls if p > 0]
        losses = [p for p in all_pnls if p <= 0]
        win_rate = len(wins) / total_trades_accum
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        
        if avg_loss < 0 and avg_win > 0:
            kelly_fraction = win_rate - ((1.0 - win_rate) / abs(avg_win / avg_loss))
        elif avg_loss == 0 and avg_win > 0:
            kelly_fraction = 1.0
            
        avg_pnl_per_trade = np.mean(all_pnls)
        avg_cost_per_trade = total_fees_accum / total_trades_accum
        if avg_cost_per_trade > 0:
            cost_coverage = avg_pnl_per_trade / avg_cost_per_trade
            
    if kelly_fraction <= 0.0:
        reason = f"Failed Tier 2: Kelly Fraction {kelly_fraction:.2f} <= 0"
        return False, 2, reason, {'kelly_fraction': float(kelly_fraction), 'cost_coverage_ratio': float(cost_coverage)}
        
    if cost_coverage < COST_COVERAGE_MULTIPLIER:
        reason = f"Failed Tier 2: Cost Coverage {cost_coverage:.1f}x < {COST_COVERAGE_MULTIPLIER}x"
        return False, 2, reason, {'kelly_fraction': float(kelly_fraction), 'cost_coverage_ratio': float(cost_coverage), 'avg_pnl': float(avg_pnl_per_trade), 'avg_cost': float(avg_cost_per_trade)}

    # -------------------------------------------------------------
    # TẦNG 3: Đời thực - Benchmark
    # -------------------------------------------------------------
    # 1. So với tiết kiệm an toàn
    if mc_cagr_mean < SAVINGS_RATE_ANNUAL:
        reason = f"Failed Tier 3: MC CAGR {mc_cagr_mean*100:.1f}% < Savings Rate {SAVINGS_RATE_ANNUAL*100:.1f}%"
        return False, 3, reason, {'mc_cagr_mean': float(mc_cagr_mean)}
        
    # 2. So với Dummy Buy & Hold (nếu có cache)
    benchmark_sharpe = -999.0
    benchmark_cagr = -999.0
    if os.path.exists(BENCHMARK_BASELINE_PATH):
        try:
            with open(BENCHMARK_BASELINE_PATH, 'r') as f:
                bmark = json.load(f)
                benchmark_sharpe = bmark.get('sharpe_mean', -999.0)
                benchmark_cagr = bmark.get('cagr_mean', -999.0)
        except Exception:
            pass
            
    if benchmark_sharpe != -999.0 and mc_sharpe_mean < benchmark_sharpe:
        reason = f"Failed Tier 3: MC Sharpe {mc_sharpe_mean:.2f} < Buy&Hold {benchmark_sharpe:.2f}"
        return False, 3, reason, {'mc_sharpe_mean': float(mc_sharpe_mean), 'benchmark_sharpe': float(benchmark_sharpe)}
        
    # -------------------------------------------------------------
    # Xếp hạng (Stressed Paths)
    # -------------------------------------------------------------
    stressed_sharpes = []
    for sim_df in stressed_paths:
        try:
            res = engine.run(strategy, sim_df)
            sh, ca, dd = calculate_metrics_for_result(res)
            stressed_sharpes.append(sh)
        except Exception:
            stressed_sharpes.append(0.0)
    mc_sharpe_stressed_mean = float(np.mean(stressed_sharpes)) if stressed_sharpes else 0.0

    # -------------------------------------------------------------
    # PASSED ALL TIERS
    # -------------------------------------------------------------
    details = {
        'ruin_rate': float(ruin_rate),
        'ruin_count': int(ruin_count),
        'total_paths': int(total_paths),
        'dd_5th_percentile': float(dd_5th),
        'kelly_fraction': float(kelly_fraction),
        'avg_pnl_per_trade': float(avg_pnl_per_trade),
        'avg_cost_per_trade': float(avg_cost_per_trade),
        'cost_coverage_ratio': float(cost_coverage),
        'total_mc_trades': int(total_trades_accum),
        'mc_cagr_mean': float(mc_cagr_mean),
        'mc_sharpe_mean': float(mc_sharpe_mean),
        'benchmark_sharpe': float(benchmark_sharpe),
        'benchmark_cagr': float(benchmark_cagr),
        'mc_sharpe_stressed_mean': mc_sharpe_stressed_mean
    }
    
    reason = f"Passed 3-Tier HMM: Ruin={ruin_rate*100:.1f}%, Kelly={kelly_fraction:.2f}, Cov={cost_coverage:.1f}x, Sharpe={mc_sharpe_mean:.2f}"
    return True, None, reason, details
