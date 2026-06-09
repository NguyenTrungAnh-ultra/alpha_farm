# Phân tích cuối cùng - reverse engineer scoring
import json, pandas as pd, numpy as np
from numpy.linalg import lstsq

with open('scoring_analysis_full.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
df = df.sort_values('score', ascending=False).reset_index(drop=True)

# Thêm derived features
df['cagr_pct'] = df['full_annual_return'] * 100
df['mdd_abs'] = df['full_max_drawdown'].abs() * 100

y = df['score'].values

print("=" * 110)
print("  BẢNG DỮ LIỆU CHÍNH — 28 chiến lược xếp theo Score")
print("=" * 110)
print(f"  {'#':>2} {'Name':<42} {'Score':>5} {'Sharpe':>7} {'CAGR':>6} {'MDD':>6} {'Calmar':>7} {'PF':>5} {'MaxC':>5} {'MeanC':>6} {'Trades':>6}")
print(f"  {'─' * 105}")
for i, r in df.iterrows():
    print(f"  {i+1:>2} {str(r['name'])[:41]:<42} {r['score']:>5} {r['full_sharpe']:>7.2f} {r['cagr_pct']:>5.1f}% {r['mdd_abs']:>5.1f}% {r['full_calmar']:>7.2f} {r['full_profit_factor']:>5.2f} {r['max_corr']:>5.2f} {r['mean_corr']:>6.3f} {r['analysis_total_trades']:>6}")

# Correlation matrix
print(f"\n\n  TƯƠNG QUAN VỚI SCORE:")
features = ['full_sharpe', 'cagr_pct', 'mdd_abs', 'full_calmar', 'full_profit_factor',
            'full_sortino', 'max_corr', 'mean_corr', 'analysis_total_trades',
            'full_volatility', 'full_cumulative_return', 'full_recovery_factor',
            'full_kelly_criterion', 'full_omega', 'full_ulcer_index']

corrs = [(f, df['score'].corr(df[f])) for f in features if f in df.columns]
corrs.sort(key=lambda x: abs(x[1]), reverse=True)
for f, c in corrs:
    bar = "█" * int(abs(c) * 30)
    sign = "+" if c > 0 else "-"
    print(f"    {f:<30} {c:>+7.3f} {sign}{bar}")

# =============================================
# NHẬN THẤY: Với 28 data points, R² rất thấp cho tất cả linear models
# → Score KHÔNG phải linear function
# → Có thể dùng RANKING-BASED hoặc NON-LINEAR
# =============================================

# Thử: Score dựa trên RANKING
print(f"\n\n  ═══ GIẢ THUYẾT: Score = f(RANK) ═══")
print(f"  Score có thể dựa trên xếp hạng tương đối (percentile) thay vì giá trị tuyệt đối")

# Tạo rank cho mỗi metric (rank 1 = tốt nhất)
df['rank_sharpe'] = df['full_sharpe'].rank(ascending=False)
df['rank_cagr'] = df['cagr_pct'].rank(ascending=False)
df['rank_mdd'] = df['mdd_abs'].rank(ascending=True)  # MDD thấp hơn = tốt hơn
df['rank_calmar'] = df['full_calmar'].rank(ascending=False)
df['rank_pf'] = df['full_profit_factor'].rank(ascending=False)
df['rank_maxcorr'] = df['max_corr'].rank(ascending=True)  # Corr thấp = tốt
df['rank_meancorr'] = df['mean_corr'].rank(ascending=True)

rank_features = ['rank_sharpe', 'rank_cagr', 'rank_mdd', 'rank_calmar', 'rank_pf', 'rank_maxcorr', 'rank_meancorr']

for rf in rank_features:
    c = df['score'].corr(df[rf])
    print(f"    Corr(Score, {rf:<20}) = {c:>+7.3f}")

# Thử regression với ranks
X = df[['rank_meancorr', 'rank_sharpe', 'rank_cagr']].values
X_aug = np.column_stack([X, np.ones(len(X))])
coefs, _, _, _ = lstsq(X_aug, y, rcond=None)
pred = X_aug @ coefs
err = y - pred
r2 = 1 - np.sum(err**2) / np.sum((y - y.mean())**2)
print(f"\n    Rank-based regression (MeanCorr_rank + Sharpe_rank + CAGR_rank): R² = {r2:.4f}")

# =============================================
# THỬ PHÂN TÍCH THEO "MARGINAL SHARPE CONTRIBUTION"
# Đây là cách quỹ lớn thường dùng
# =============================================
print(f"\n\n  ═══ GIẢ THUYẾT: Score dựa trên Marginal Portfolio Contribution ═══")
print(f"  Công thức quỹ: Score ∝ (Strategy Sharpe) * (1 - avg_correlation_to_portfolio)")
print(f"  Tức là: Score ∝ Sharpe * Diversification_Benefit")

df['diversity_benefit'] = 1 - df['mean_corr']
df['marginal_sharpe'] = df['full_sharpe'] * df['diversity_benefit']

c = df['score'].corr(df['marginal_sharpe'])
print(f"\n    Corr(Score, Marginal_Sharpe) = {c:>+7.3f}")

# Thử các combo
combos = [
    ('Sharpe * (1 - MeanCorr)', df['full_sharpe'] * (1 - df['mean_corr'])),
    ('Calmar * (1 - MeanCorr)', df['full_calmar'] * (1 - df['mean_corr'])),
    ('CAGR * (1 - MeanCorr)', df['cagr_pct'] * (1 - df['mean_corr'])),
    ('PF * (1 - MeanCorr)', df['full_profit_factor'] * (1 - df['mean_corr'])),
    ('Kelly * (1 - MeanCorr)', df['full_kelly_criterion'] * (1 - df['mean_corr'])),
    ('Sharpe * (1 - MaxCorr)', df['full_sharpe'] * (1 - df['max_corr'])),
    ('Recovery * (1 - MeanCorr)', df['full_recovery_factor'] * (1 - df['mean_corr'])),
    ('Sharpe / (1 + MeanCorr)', df['full_sharpe'] / (1 + df['mean_corr'])),
    ('CAGR / MDD * (1-MeanCorr)', (df['cagr_pct'] / df['mdd_abs']) * (1 - df['mean_corr'])),
    ('log(Trades) * (1-MeanCorr)', np.log1p(df['analysis_total_trades']) * (1 - df['mean_corr'])),
]

print(f"\n  {'Metric Combo':<40} {'Corr(Score)':>12} {'R²_linear':>10}")
print(f"  {'─' * 65}")

for name, series in combos:
    c = df['score'].corr(series)
    # Quick R² 
    X = series.values.reshape(-1, 1)
    X_aug = np.column_stack([X, np.ones(len(X))])
    coefs_tmp, _, _, _ = lstsq(X_aug, y, rcond=None)
    pred_tmp = X_aug @ coefs_tmp
    r2_tmp = 1 - np.sum((y - pred_tmp)**2) / np.sum((y - y.mean())**2)
    print(f"  {name:<40} {c:>+12.4f} {r2_tmp:>10.4f}")

print(f"\n\n{'=' * 110}")
print("  KẾT LUẬN CUỐI CÙNG")
print("=" * 110)
print("""
  DỮ LIỆU CHO THẤY:
  
  1. R² tối đa chỉ ~0.18 cho mọi model tuyến tính → Scoring KHÔNG PHẢI linear
  
  2. Performance metrics (Sharpe, CAGR, Calmar) có tương quan YẾU hoặc ÂM với Score:
     - Sharpe ↔ Score = -0.27  (!)
     - Kelly  ↔ Score = -0.42  (!)
     - Trades ↔ Score = +0.50  (mạnh nhất)
  
  3. Các chiến lược CỰC TỐT nhưng score CỰC THẤP:
     - ADX Following: Sharpe=2.20, CAGR=63.8% → Score=6 (!)
     - Momentum_LinRegAngle: Sharpe=2.40, CAGR=66.4% → Score=3 (!)
  
  4. GIẢI THÍCH KHẢ THI NHẤT:
     Score phụ thuộc mạnh vào THỨ TỰ NỘP BÀI trên nền tảng.
     Hệ thống dùng "incremental portfolio optimization":
     - Chiến lược nộp đầu tiên → Base score thấp (chưa có portfolio)
     - Mỗi chiến lược nộp sau → Score = Marginal contribution vào portfolio TÍCH LŨY
     - Nếu nộp sau nhưng corr cao với portfolio → bị phạt nặng
     - Nếu nộp sau nhưng corr thấp → được thưởng lớn
     
  5. ĐỀ XUẤT CHIẾN LƯỢC THI:
     a) KHÔNG nên chạy theo Sharpe/CAGR cao nhất
     b) Ưu tiên chiến lược CÓ LOGIC KHÁC BIỆT (corr thấp)
     c) THỨ TỰ NỘP RẤT QUAN TRỌNG — nộp chiến lược "khác biệt nhất" cuối cùng
     d) Số lượng trades cũng có vẻ ảnh hưởng tích cực
""")
