"""Sinh các hình cho thesis proposal từ dữ liệu thật của dự án.

Chạy từ thư mục gốc repo:  python docs/proposal/thesis_proposal/make_figures.py
Số liệu hình 2 và 3 lấy từ 3tier_results.csv và phép đo regime (scratchpad/regime_check.py).
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "font.family": "serif", "font.size": 10, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.6,
})

# ── Hình 1: giá VN30F1M và phân chia dữ liệu ─────────────────────────────────
df = pd.read_csv(os.path.join(ROOT, "data", "DNSE_VN30F_1H.csv"), index_col=0, parse_dates=True)
close = df["Close"].resample("D").last().dropna()
fig, ax = plt.subplots(figsize=(7.2, 3.0))
periods = [("2018-08-13", "2020-01-01", "Warm-up", "#f1f0ec"),
           ("2020-01-01", "2024-01-01", "Search (in-sample)", "#e3edf9"),
           ("2024-01-01", "2025-01-01", "Valid.", "#fbe6dc"),
           ("2025-01-01", "2025-12-31", "Test", "#dcf2e8")]
for a, b, name, c in periods:
    ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=c, lw=0, zorder=0)
    ax.text(pd.Timestamp(a) + (pd.Timestamp(b) - pd.Timestamp(a)) / 2, 2150, name,
            ha="center", va="top", fontsize=8, color=INK2)
ax.plot(close.index, close.values, color=BLUE, lw=1.4, zorder=2)
ax.set_ylabel("VN30F1M close (index points)")
ax.set_ylim(500, 2200)
ax.grid(axis="x", visible=False)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "vn30f_split.png"), dpi=300)
plt.close(fig)

# ── Hình 2: phễu kiểm định 3 tầng (171 chiến lược thế hệ đầu) ───────────────
t = pd.read_csv(os.path.join(ROOT, "3tier_results.csv"))
n = len(t)
passed_t1 = (t.status != "FAIL TIER 1").sum()
passed_t2 = (~t.status.isin(["FAIL TIER 1", "FAIL TIER 2"])).sum()
passed_all = (t.status == "PASS").sum()
stages = ["Candidates", "Pass Tier 1\n(survival)", "Pass Tier 2\n(edge after costs)", "Pass Tier 3\n(opportunity cost)"]
vals = [n, passed_t1, passed_t2, passed_all]
fig, ax = plt.subplots(figsize=(6.4, 2.6))
bars = ax.barh(stages[::-1], vals[::-1], color=BLUE, height=0.55)
for b, v in zip(bars, vals[::-1]):
    ax.text(b.get_width() + 2, b.get_y() + b.get_height() / 2, f"{v}", va="center", color=INK, fontsize=9)
ax.set_xlabel("Number of strategies")
ax.set_xlim(0, n * 1.12)
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "three_tier_funnel.png"), dpi=300)
plt.close(fig)
print("funnel:", vals)

# ── Hình 3: độ dài chế độ biến động cao, thật vs giả lập ─────────────────────
tfs = ["1m", "5m", "15m", "60m"]
real = [10.3, 40.3, 40.2, 61.9]
synth = [9.4, 34.6, 34.5, 44.8]
x = range(len(tfs))
w = 0.36
fig, ax = plt.subplots(figsize=(6.0, 2.8))
b1 = ax.bar([i - w / 2 - 0.01 for i in x], real, w, color=BLUE, label="Historical")
b2 = ax.bar([i + w / 2 + 0.01 for i in x], synth, w, color=ORANGE, label="HMM synthetic (mean of 10 paths)")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1, f"{b.get_height():.1f}",
                ha="center", va="bottom", fontsize=8, color=INK)
ax.set_xticks(list(x), tfs)
ax.set_xlabel("Bar frequency")
ax.set_ylabel("Mean duration (bars)")
ax.set_ylim(0, 75)
ax.grid(axis="x", visible=False)
ax.legend(frameon=False, fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "regime_duration.png"), dpi=300)
plt.close(fig)

# ── Hình 4: các cửa sổ walk-forward (tìm 2 năm, đánh giá 6 tháng, trượt 6 tháng) ─
eval_starts = pd.date_range("2020-07-01", "2025-07-01", freq="6MS")
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.2, 4.4), sharex=True,
                               gridspec_kw={"height_ratios": [1, 1.6]})
ax1.plot(close.index, close.values, color=INK2, lw=1.0)
ax1.set_ylabel("VN30F1M close")
ax1.grid(axis="x", visible=False)
for i, e in enumerate(eval_starts):
    s = max(e - pd.DateOffset(years=2), pd.Timestamp("2018-08-13"))
    f = e + pd.DateOffset(months=6)
    y = len(eval_starts) - 1 - i
    ax2.barh(y, (e - s).days, left=s, height=0.62, color=BLUE)
    ax2.barh(y, (f - e).days, left=e, height=0.62, color=ORANGE)
ax2.set_yticks(range(len(eval_starts)), [f"W{len(eval_starts) - k}" for k in range(len(eval_starts))])
ax2.set_ylabel("Window")
ax2.grid(axis="y", visible=False)
ax2.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=ORANGE)],
           labels=["Search (2 years)", "Out-of-sample evaluation (6 months)"],
           frameon=False, fontsize=8, loc="upper left", ncol=2, bbox_to_anchor=(0, 1.13))
fig.tight_layout()
fig.savefig(os.path.join(OUT, "walk_forward.png"), dpi=300)
plt.close(fig)
print("walk-forward windows:", len(eval_starts))
