"""
central_config
==============
Central configuration module for Alpha Farm.

Defines global parameters including project roots, environment variables, centralized 
strategy quality thresholds, backtesting settings, VN30F1M contract specifications, 
trading fees, leverage margins, default capitals, and CSV pathing templates.
"""

import os
from dotenv import load_dotenv

# Automatically resolve PROJECT_ROOT to the directory containing main.py (two levels up from this file)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Centralized Quality Thresholds for MCTS (Search Gradient)
MCTS_QUALITY_THRESHOLDS = {
    'sharpe_ratio': 1.3,
    'cagr': 0.15,
    'max_drawdown_pct': -35.0,
    'profit_factor': 1.3,
    'calmar_ratio': 1.1
}

# General App Config
MAX_CORRELATION = 0.5

# === MCTS One-pass Pipeline Config ===
REWARD_WEIGHTS = {
    'calmar_weight': 0.6,
    'ic_weight': 0.4,
    'max_ic': 0.15,
    'max_calmar': 3.0,
    'burn_in': 15000,
    'entropy_threshold': 0.15,
    'patience': 5000
}

# === HMM Monte Carlo Validation Config ===
HMM_COMPONENTS = 3
HMM_STRESS_FACTOR = 1.5
HMM_BLOCK_SIZE = 20
HMM_PATHS_PER_TF = 500
MC_CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "MCdata")

# === 3-Tier Realistic Validation Config ===
# Tier 1: Margin Call limit (% equity drawdown)
MARGIN_CALL_DD_THRESHOLD = -23.0
# Tier 1: Max allowed percentage of paths hitting Margin Call
RUIN_RATE_THRESHOLD = 0.05

# Tier 2: Cost Coverage multiplier (avg_pnl >= k * avg_cost)
COST_COVERAGE_MULTIPLIER = 3.0

# Tier 3: Annual risk-free savings rate for opportunity cost comparison
SAVINGS_RATE_ANNUAL = 0.06
# Tier 3: Cache path for Dummy Buy & Hold Benchmark
BENCHMARK_BASELINE_PATH = os.path.join(PROJECT_ROOT, 'results', 'benchmark_hmm_baseline.json')
# === Thông số hợp đồng VN30F1M ===
MULTIPLIER = 100_000               # VND/điểm (chuẩn VN30F1M)
TICK_SIZE = 0.1                    # Bước giá tối thiểu

# === Phí giao dịch & Đáo hạn ===
FEE_PER_CONTRACT_PER_SIDE = 6_000  # VND/HĐ/chiều (đã calibrate chính xác)
ROLLOVER_PENALTY_POINTS = 2.0      # Phí Basis Spread khi giữ lệnh qua ngày đáo hạn (2.0 điểm = 200,000 VND)

# === Margin / Leverage ===
MARGIN_RATE = 0.285                # Tỷ lệ ký quỹ (28.5%)
MAINTENANCE_MARGIN_RATE = 0.20     # Tỷ lệ ký quỹ duy trì (Maintenance Margin)

# === Vốn mặc định ===
INITIAL_CAPITAL = 1_000_000_000    # 1 tỷ VND

# === Khoảng backtest ===
BACKTEST_START = '2020-01-01'
BACKTEST_END = '2025-01-01'

# === Khung thời gian hỗ trợ ===
SUPPORTED_TIMEFRAMES = ['1m', '3m', '5m', '10m', '15m', '30m', '60m']

# === MCTS Timeframe Scaling ===
# Baseline: 10m (scale=1.0). Các khung khác scale theo tỷ lệ phút.
BASELINE_TF_MINUTES = 10

TIMEFRAME_MINUTES = {
    '1m': 1, '3m': 3, '5m': 5, '10m': 10,
    '15m': 15, '30m': 30, '60m': 60
}

# Base periods (at 10m baseline)
BASE_PERIODS = [5, 10, 14, 20, 30, 60]
BASE_WINDOW_SEARCH = [5, 10, 14, 20, 30, 40, 60]

# Configurable MCTS iteration count
MCTS_ITERATIONS = 50000

# === Data path template ===
DATA_DIR = 'data'
DATA_FILENAME_TEMPLATE = 'DNSE_VN30F_{timeframe}.csv'
