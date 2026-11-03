"""Regenerate the thesis figures from the result files.

Run from the repo root:  .venv/Scripts/python.exe docs/thesis/make_figures.py
Writes PNGs into docs/thesis/figures/ and prints the numbers used as sanity checks.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from strategy_workflows.WalkForward import (WINDOWS, annualised_sharpe,  # noqa: E402
                                            real_daily_series)

WF = os.path.join(ROOT, "results", "walkforward")
PL = os.path.join(ROOT, "results", "planted_rq1")
OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "font.family": "serif", "font.size": 10, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "figure.facecolor": "white", "savefig.facecolor": "white",
})

SYSTEMS = ["llm_mcts", "mcts_only", "random", "llm_only", "buy_hold", "tsmom"]
NAMES = {"llm_mcts": "LLM + MCTS", "mcts_only": "MCTS only", "random": "Random search",
         "llm_only": "LLM only", "buy_hold": "Buy-and-hold", "tsmom": "TSMOM"}
COLORS = {"llm_mcts": "#2a78d6", "mcts_only": "#eb6834", "random": "#7a7a76",
          "llm_only": "#2f9e6e", "buy_hold": "#8d5fc7", "tsmom": "#c9a227"}
SEARCH = ["llm_mcts", "mcts_only", "random"]


# ── shared loaders ──────────────────────────────────────────────────────────
def load_returns(system):
    return pd.read_csv(os.path.join(WF, system, "returns.csv"), parse_dates=["date"])


def load_runs(system):
    runs = pd.read_csv(os.path.join(WF, system, "runs.csv"), usecols=["mode", "window", "seed", "eval_sharpe"])
    return runs[runs["mode"] == "real"].drop_duplicates(["window", "seed"], keep="last")


def real_series(system):
    """5-seed daily mean for the search configurations, seed 1 for the deterministic ones."""
    return real_daily_series(load_returns(system))


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches="tight")
    plt.close(fig)


def planted_summary():
    return pd.read_csv(os.path.join(PL, "summary.csv"))


# ── figures ─────────────────────────────────────────────────────────────────
def fig_windows():
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for i, w in enumerate(WINDOWS):
        y = len(WINDOWS) - i
        s0, te, se, ee = (pd.Timestamp(w.search_start), pd.Timestamp(w.train_end),
                          pd.Timestamp(w.search_end), pd.Timestamp(w.eval_end))
        for a, b, c, lab in [(s0, te, "#9db9e0", "Training"), (te, se, "#f2b494", "Validation (12 months)"),
                             (se, ee, "#5fbb8f", "Evaluation (6 months)")]:
            ax.barh(y, (b - a).days, left=mdates.date2num(a), height=0.55, color=c,
                    label=lab if i == 0 else None)
    ax.set_yticks(range(len(WINDOWS), 0, -1))
    ax.set_yticklabels([f"Window {i + 1}" for i in range(len(WINDOWS))])
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlabel("Date")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, frameon=False, fontsize=8)
    fig.tight_layout()
    save(fig, "wf_windows.png")


def fig_placebo():
    s = pd.read_csv(os.path.join(WF, "llm_mcts", "summary.csv"))
    placebo = s[s["mode"] == "placebo"]["sharpe"].dropna()
    real1 = s[s["mode"] == "real_seed1"].iloc[0]
    mean5 = s[s["mode"] == "real_mean"]["sharpe"].iloc[0]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bins = np.arange(np.floor(placebo.min() * 4) / 4, np.ceil(max(placebo.max(), real1["sharpe"]) * 4) / 4 + 0.25, 0.25)
    ax.hist(placebo, bins=bins, color="#b5b4af", edgecolor="white", label=f"Placebo sets (n = {len(placebo)})")
    ax.axvline(real1["sharpe"], color=COLORS["llm_mcts"], lw=2, label=f"Real, seed 1 ({real1['sharpe']:.2f})")
    ax.axvline(mean5, color=COLORS["llm_mcts"], lw=1.6, ls="--", label=f"Real, 5-seed mean ({mean5:.2f}, descriptive)")
    ax.text(real1["sharpe"] + 0.03, ax.get_ylim()[1] * 0.97, f"p = {real1['p_value']:.2f}",
            va="top", fontsize=9, color=INK)
    ax.set_xlabel("Out-of-sample Sharpe ratio")
    ax.set_ylabel("Number of placebo sets")
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    save(fig, "placebo.png")
    print(f"placebo: real_seed1={real1['sharpe']:.4f} real_mean={mean5:.4f} placebo_max={placebo.max():.4f} "
          f"p={real1['p_value']} n={len(placebo)}")


def fig_equity():
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    for sys_ in SYSTEMS:
        r = real_series(sys_)
        ax.plot(r.index, r.cumsum() * 100, color=COLORS[sys_], lw=1.4, label=NAMES[sys_])
        print(f"mean-series Sharpe {sys_}: {annualised_sharpe(r):.4f}")
    for w in WINDOWS[1:]:
        ax.axvline(pd.Timestamp(w.search_end) + pd.Timedelta(days=1), color="#c9c8c3", lw=0.7, zorder=0)
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_ylabel("Cumulative out-of-sample return (%)")
    ax.set_xlabel("Date")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper left")
    fig.tight_layout()
    save(fig, "oos_equity.png")


def fig_window_sharpe():
    n = len(WINDOWS)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    width = 0.13
    for k, sys_ in enumerate(SYSTEMS):
        m = load_runs(sys_).groupby("window")["eval_sharpe"].mean().reindex(range(1, n + 1))
        ax.bar(np.arange(1, n + 1) + (k - 2.5) * width, m.values, width, color=COLORS[sys_], label=NAMES[sys_])
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_xticks(range(1, n + 1))
    ax.set_xlabel("Walk-forward window")
    ax.set_ylabel("Out-of-sample Sharpe ratio")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper left")
    fig.tight_layout()
    save(fig, "window_sharpe.png")


def fig_seed_sharpe():
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for x, sys_ in enumerate(SYSTEMS):
        ret = load_returns(sys_)
        real = ret[ret["mode"] == "real"].drop_duplicates(["date", "window", "seed", "mode", "placebo_set"], keep="last")
        per_seed = real.groupby("seed").apply(
            lambda g: annualised_sharpe(g.groupby("date")["return"].mean()), include_groups=False)
        ax.scatter(np.full(len(per_seed), x) + np.linspace(-0.12, 0.12, len(per_seed)) * (len(per_seed) > 1),
                   per_seed.values, color=COLORS[sys_], s=28, zorder=3,
                   label="Single seed" if x == 0 else None)
        if sys_ in SEARCH:
            ax.scatter([x + 0.28], [annualised_sharpe(real_series(sys_))], marker="D", s=40,
                       facecolor="white", edgecolor=COLORS[sys_], lw=1.6, zorder=3,
                       label="5-seed mean series" if x == 0 else None)
        print(f"per-seed Sharpe {sys_}: {np.round(per_seed.values, 3).tolist()}")
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_xticks(range(len(SYSTEMS)))
    ax.set_xticklabels([NAMES[s] for s in SYSTEMS], rotation=20, ha="right")
    ax.set_ylabel("Full-period out-of-sample Sharpe ratio")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=8, loc="upper left", scatterpoints=1)
    fig.tight_layout()
    save(fig, "seed_sharpe.png")


def fig_planted_budget():
    s = planted_summary()
    s = s[s["ic"] == 0.1]
    fig, axes = plt.subplots(1, 4, figsize=(8.4, 2.9), sharey=True)
    for ax, a in zip(axes, ["A1", "A2", "A3", "A4"]):
        for sys_ in SEARCH:
            d = s[(s["a"] == a) & (s["config"] == sys_)].sort_values("budget")
            ax.plot(d["budget"] / 1000, d["near_count"], marker="o", ms=4, lw=1.4,
                    color=COLORS[sys_], label=NAMES[sys_])
        ax.axvline(50, color=INK2, ls=":", lw=1)
        ax.set_title(a, fontsize=10)
        ax.set_xticks([10, 25, 50, 75, 100])
        ax.set_xlabel("Budget (k evaluations)")
    axes[0].set_ylabel("Near-recovery (out of 10 seeds)")
    axes[0].set_ylim(-0.3, 10.3)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "planted_budget.png")
    d = s[s["budget"] == 100000].pivot(index="a", columns="config", values="near_count")
    print("near count at 100k, IC 0.1:\n", d[SEARCH])


def fig_planted_ic():
    s = planted_summary()
    s = s[s["budget"] == 100000]
    ics = [0.0, 0.05, 0.1]
    fig, axes = plt.subplots(1, 4, figsize=(8.4, 2.9), sharey=True)
    for ax, a in zip(axes, ["A1", "A2", "A3", "A4"]):
        for k, sys_ in enumerate(SEARCH):
            d = s[(s["a"] == a) & (s["config"] == sys_)].set_index("ic").reindex(ics)
            ax.bar(np.arange(3) + (k - 1) * 0.27, d["near_count"], 0.27, color=COLORS[sys_], label=NAMES[sys_])
        ax.set_title(a, fontsize=10)
        ax.set_xticks(range(3))
        ax.set_xticklabels(["0", "0.05", "0.1"])
        ax.set_xlabel("Planted IC")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Near-recovery at 100k (out of 10 seeds)")
    axes[0].set_ylim(0, 10.3)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "planted_ic.png")


if __name__ == "__main__":
    fig_windows()
    fig_placebo()
    fig_equity()
    fig_window_sharpe()
    fig_seed_sharpe()
    fig_planted_budget()
    fig_planted_ic()
    print("written:", sorted(os.listdir(OUT)))
