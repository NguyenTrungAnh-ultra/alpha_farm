import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine import load_data, XNOBacktestEngine
from scratch.run_local_meanrev import MeanRev_CCI_LinearReg

df = load_data('30m', start='2020-01-01', end='2025-01-01')
engine = XNOBacktestEngine()
res = engine.run(MeanRev_CCI_LinearReg(), df)

trades = res.trades
pnls = [t.net_pnl for t in trades]
wins = [p for p in pnls if p > 0]
losses = [p for p in pnls if p <= 0]

avg_win = np.mean(wins) if wins else 0
avg_loss = np.mean(losses) if losses else 0

print(f"Wins count: {len(wins)}, Losses count: {len(losses)}")
print(f"Avg Win: {avg_win:,.2f}")
print(f"Avg Loss: {avg_loss:,.2f}")
print(f"Ratio of Avg Win / Avg Loss: {abs(avg_win / avg_loss):.8f}")

# What if win_loss_ratio is calculated using gross_pnl?
gross_wins = [t.gross_pnl for t in trades if t.gross_pnl > 0]
gross_losses = [t.gross_pnl for t in trades if t.gross_pnl <= 0]
avg_gross_win = np.mean(gross_wins) if gross_wins else 0
avg_gross_loss = np.mean(gross_losses) if gross_losses else 0
print(f"Ratio of Avg Gross Win / Avg Gross Loss: {abs(avg_gross_win / avg_gross_loss):.8f}")

# What if win_loss_ratio is calculated as win_rate / loss_rate?
win_rate = len(wins) / len(trades)
loss_rate = len(losses) / len(trades)
print(f"Win/Loss count ratio: {win_rate / loss_rate:.8f}")

# What if we use percentage returns of trades?
running_eq = 1e9
pct_returns = []
for t in trades:
    # XNO percent return of a trade is: net_pnl / running_equity
    pct_returns.append(t.net_pnl / running_eq)
    running_eq += t.net_pnl

win_pcts = [p for p in pct_returns if p > 0]
loss_pcts = [p for p in pct_returns if p <= 0]

avg_win_pct = np.mean(win_pcts) if win_pcts else 0
avg_loss_pct = np.mean(loss_pcts) if loss_pcts else 0

print(f"Avg Win Pct: {avg_win_pct:.8f}")
print(f"Avg Loss Pct: {avg_loss_pct:.8f}")
print(f"Ratio of Avg Win Pct / Avg Loss Pct: {abs(avg_win_pct / avg_loss_pct):.8f}")
