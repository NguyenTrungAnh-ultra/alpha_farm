"""
XNOQuant Engine — Calibrated Constants
=======================================
Tham số đã reverse-engineer từ 8 bài test trên nền tảng XNOQuant.
"""

# === Thông số hợp đồng VN30F1M ===
MULTIPLIER = 100_000               # VND/điểm (chuẩn VN30F1M)
TICK_SIZE = 0.1                    # Bước giá tối thiểu

# === Phí giao dịch ===
FEE_PER_CONTRACT_PER_SIDE = 6_000  # VND/HĐ/chiều (đã calibrate chính xác)

# === Margin / Leverage ===
MARGIN_RATE = 0.285                # Tỷ lệ ký quỹ (~28.5%, leverage ~3.5x)

# === Vốn mặc định ===
INITIAL_CAPITAL = 1_000_000_000    # 1 tỷ VND (chuẩn XNOQuant)

# === Khoảng backtest ===
BACKTEST_START = '2020-01-01'
BACKTEST_END = '2025-01-01'

# === Khung thời gian hỗ trợ ===
SUPPORTED_TIMEFRAMES = ['1m', '3m', '5m', '10m', '15m', '30m', '60m']

# === Data path template ===
DATA_DIR = 'data'
DATA_FILENAME_TEMPLATE = 'DNSE_VN30F_{timeframe}.csv'
