"""
XNOQuant Engine — Performance Metrics
========================================
Tính toán tất cả chỉ số hiệu suất hiển thị trên nền tảng XNOQuant.
"""

import pandas as pd
import numpy as np
from backtest.engine import BacktestResult


def compute_metrics(result: BacktestResult) -> dict:
    """
    Tính toán toàn bộ performance metrics giống XNOQuant.

    Returns
    -------
    dict
        Dictionary chứa 3 nhóm metrics:
        - Transaction Analysis
        - Performance Metrics
        - Advanced Metrics
    """
    trades = result.trades
    equity = result.equity_curve.dropna()
    initial = result.initial_capital

    # === TRANSACTION ANALYSIS ===
    total_trades = result.total_trades  # XNO counts each position change as 1 trade

    n_completed = len(trades)  # Completed round-trips (have both entry and exit)

    if n_completed > 0:
        pnls = [t.net_pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        # Win/Loss dưới dạng % equity tại thời điểm trade
        pnl_pcts = []
        running_eq = initial
        for t in trades:
            pct = t.net_pnl / running_eq * 100 if running_eq != 0 else 0
            pnl_pcts.append(pct)
            running_eq += t.net_pnl

        win_pcts = [p for p in pnl_pcts if p > 0]
        loss_pcts = [p for p in pnl_pcts if p <= 0]

        largest_win = max(win_pcts) if win_pcts else 0.0
        largest_loss = min(loss_pcts) if loss_pcts else 0.0
        avg_win = np.mean(win_pcts) if win_pcts else 0.0
        avg_loss = np.mean(loss_pcts) if loss_pcts else 0.0
    else:
        pnls = []
        wins = []
        losses = []
        pnl_pcts = []
        largest_win = 0.0
        largest_loss = 0.0
        avg_win = 0.0
        avg_loss = 0.0

    # Net Equity & PnL
    net_equity = result.final_equity
    total_profit_pct = (net_equity / initial - 1) * 100
    total_fees_pct = result.total_fees / initial * 100

    # Unrealized PnL (nếu có vị thế mở cuối backtest)
    unrealized_pnl = net_equity - initial - sum(pnls) if n_completed > 0 else net_equity - initial

    # Initial Capital display (XNO trừ phí bar 0 nếu có)
    displayed_initial = initial
    if n_completed > 0 and trades[0].entry_bar == 0:
        # Trade xảy ra ở bar đầu tiên -> trừ phí opening
        first_open_fee = trades[0].contracts * 6000  # fee_per_contract
        displayed_initial = initial - first_open_fee

    # === PERFORMANCE METRICS ===
    cumulative_return = total_profit_pct

    # CAGR
    if len(equity) > 1:
        n_bars = len(equity)
        # Ước tính số năm từ index
        total_seconds = (equity.index[-1] - equity.index[0]).total_seconds()
        years = total_seconds / (365.25 * 24 * 3600)
        if years > 0 and net_equity > 0:
            cagr = (net_equity / initial) ** (1 / years) - 1
        else:
            cagr = 0.0
    else:
        cagr = 0.0

    # Win Rate
    win_rate = len(wins) / n_completed * 100 if n_completed > 0 else 0.0

    # Profit Factor
    gross_profit = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    # Returns series (bar-by-bar)
    returns = equity.pct_change().dropna()
    returns = returns.replace([np.inf, -np.inf], 0)

    # Sharpe Ratio (annualized)
    if len(returns) > 1 and returns.std() > 0:
        # Tính bars per year dựa trên timeframe
        bars_per_day = _estimate_bars_per_day(equity.index)
        trading_days_per_year = 252
        bars_per_year = bars_per_day * trading_days_per_year
        sharpe = returns.mean() / returns.std() * np.sqrt(bars_per_year)
    else:
        sharpe = 0.0

    # Sortino Ratio
    if len(returns) > 1:
        downside = returns[returns < 0]
        downside_std = downside.std() if len(downside) > 0 else 0
        if downside_std > 0:
            sortino = returns.mean() / downside_std * np.sqrt(bars_per_year)
        else:
            sortino = float('inf') if returns.mean() > 0 else 0.0
    else:
        sortino = 0.0

    # Max Drawdown
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_drawdown = drawdown.min() * 100

    # Calmar Ratio
    calmar = cagr / abs(max_drawdown / 100) if max_drawdown != 0 else 0.0

    # Payoff Ratio
    payoff = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # Volatility (annualized std of returns)
    if len(returns) > 1:
        volatility = returns.std() * np.sqrt(bars_per_year)
    else:
        volatility = 0.0

    # === ADVANCED METRICS ===

    # Recovery Factor
    if max_drawdown != 0:
        max_dd_abs = abs(drawdown.min()) * initial
        recovery_factor = sum(pnls) / max_dd_abs if max_dd_abs > 0 else 0.0
    else:
        recovery_factor = 0.0

    # Kelly Criterion
    if n_completed > 0:
        win_prob = len(wins) / n_completed
        if avg_loss != 0:
            kelly = win_prob - (1 - win_prob) / abs(avg_win / avg_loss) if avg_win != 0 else 0
        else:
            kelly = win_prob
    else:
        kelly = 0.0

    # Omega Ratio (threshold = 0)
    if len(returns) > 0:
        gains = returns[returns > 0].sum()
        losses_sum = abs(returns[returns < 0].sum())
        omega = gains / losses_sum if losses_sum > 0 else float('inf')
    else:
        omega = 0.0

    # Ulcer Index
    if len(equity) > 0:
        dd_pct = ((equity - rolling_max) / rolling_max * 100)
        ulcer_index = np.sqrt((dd_pct ** 2).mean())
    else:
        ulcer_index = 0.0

    # VaR (5%, parametric)
    if len(returns) > 1:
        var_95 = np.percentile(returns, 5) * 100
    else:
        var_95 = 0.0

    # CVaR (Expected Shortfall)
    if len(returns) > 1:
        threshold = np.percentile(returns, 5)
        cvar = returns[returns <= threshold].mean() * 100 if len(returns[returns <= threshold]) > 0 else 0.0
    else:
        cvar = 0.0

    return {
        # Transaction Analysis
        'initial_capital': displayed_initial,
        'net_equity': net_equity,
        'total_profit_pct': total_profit_pct,
        'total_fees_pct': total_fees_pct,
        'total_trades': total_trades,
        'largest_win_pct': largest_win,
        'largest_loss_pct': largest_loss,
        'avg_win_pct': avg_win,
        'avg_loss_pct': avg_loss,
        'unrealized_pnl': unrealized_pnl,

        # Performance Metrics
        'cumulative_return_pct': cumulative_return,
        'cagr_pct': cagr * 100,
        'win_rate_pct': win_rate,
        'profit_factor': profit_factor,
        'sharpe_ratio': sharpe,
        'sortino_ratio': sortino,
        'calmar_ratio': calmar,
        'payoff_ratio': payoff,
        'volatility': volatility,
        'max_drawdown_pct': max_drawdown,

        # Advanced Metrics
        'recovery_factor': recovery_factor,
        'kelly_criterion_pct': kelly * 100,
        'omega_ratio': omega,
        'ulcer_index': ulcer_index,
        'var_95_pct': var_95,
        'cvar_95_pct': cvar,

        # Raw data
        'total_fees_vnd': result.total_fees,
        'total_pnl_vnd': sum(pnls),
    }


def _estimate_bars_per_day(index: pd.DatetimeIndex) -> float:
    """Ước tính số bar trung bình mỗi ngày giao dịch."""
    if len(index) < 2:
        return 1
    dates = index.date
    unique_dates = pd.Series(dates).nunique()
    if unique_dates == 0:
        return 1
    return len(index) / unique_dates


def print_report(result: BacktestResult) -> None:
    """In báo cáo hiệu suất giống giao diện XNOQuant."""
    m = compute_metrics(result)

    print()
    print("=" * 75)
    print("  XNOQuant Local Backtest Report")
    print("=" * 75)

    # Transaction Analysis
    print()
    print("  ┌─── Transaction Analysis ──────────────────────────────────┐")
    print(f"  │  Initial Capital     {m['initial_capital']:>20,.0f} đ       │")
    print(f"  │  Net Equity          {m['net_equity']:>20,.0f} đ       │")
    print(f"  │  Total Profit        {m['total_profit_pct']:>+19.2f} %       │")
    print(f"  │  Total Fees          {m['total_fees_pct']:>+19.2f} %       │")
    print(f"  │  Total Trades        {m['total_trades']:>20}         │")
    print(f"  │  Largest Win         {m['largest_win_pct']:>+19.2f} %       │")
    print(f"  │  Largest Loss        {m['largest_loss_pct']:>+19.2f} %       │")
    print(f"  │  Avg Win             {m['avg_win_pct']:>+19.2f} %       │")
    print(f"  │  Avg Loss            {m['avg_loss_pct']:>+19.2f} %       │")
    print(f"  │  Unrealized PnL      {m['unrealized_pnl']:>20,.0f} đ       │")
    print("  └──────────────────────────────────────────────────────────┘")

    # Performance Metrics
    print()
    print("  ┌─── Performance Metrics ───────────────────────────────────┐")
    print(f"  │  Cumulative Return   {m['cumulative_return_pct']:>+19.2f} %       │")
    print(f"  │  CAGR                {m['cagr_pct']:>+19.2f} %       │")
    print(f"  │  Win Rate            {m['win_rate_pct']:>+19.2f} %       │")
    print(f"  │  Profit Factor       {m['profit_factor']:>20.2f}         │")
    print(f"  │  Sharpe Ratio        {m['sharpe_ratio']:>20.2f}         │")
    print(f"  │  Sortino Ratio       {m['sortino_ratio']:>20.2f}         │")
    print(f"  │  Calmar Ratio        {m['calmar_ratio']:>20.2f}         │")
    print(f"  │  Payoff Ratio        {m['payoff_ratio']:>20.2f}         │")
    print(f"  │  Volatility          {m['volatility']:>20.2f}         │")
    print(f"  │  Max Drawdown        {m['max_drawdown_pct']:>+19.2f} %       │")
    print("  └──────────────────────────────────────────────────────────┘")

    # Advanced Metrics
    print()
    print("  ┌─── Advanced Metrics ──────────────────────────────────────┐")
    print(f"  │  Recovery Factor     {m['recovery_factor']:>20.2f}         │")
    print(f"  │  Kelly Criterion     {m['kelly_criterion_pct']:>+19.2f} %       │")
    print(f"  │  Omega Ratio         {m['omega_ratio']:>20.2f}         │")
    print(f"  │  Ulcer Index         {m['ulcer_index']:>20.2f}         │")
    print(f"  │  VaR                 {m['var_95_pct']:>+19.2f} %       │")
    print(f"  │  CVaR                {m['cvar_95_pct']:>+19.2f} %       │")
    print("  └──────────────────────────────────────────────────────────┘")
    print()
