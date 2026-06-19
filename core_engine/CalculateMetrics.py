"""
XNOQuant Engine — Performance Metrics
========================================
Tính toán tất cả chỉ số hiệu suất hiển thị trên nền tảng XNOQuant.
"""

import pandas as pd
import numpy as np
from core_engine.BacktestEngine import BacktestResult


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

    # Initial Capital display (XNO trừ phí mở lệnh đầu tiên)
    displayed_initial = initial - result.first_trade_open_fee

    # Resample equity to daily frequency (last bar of each trading day)
    daily_equity = equity.resample('D').last().dropna()
    
    # XNOQuant computes rolling returns for Volatility, Sortino, VaR, CVaR, etc.
    daily_returns_rolling = daily_equity.pct_change().fillna(0.0)
    daily_returns_rolling = daily_returns_rolling.replace([np.inf, -np.inf], 0)
    
    # XNOQuant computes constant capital returns specifically for the Sharpe Ratio:
    # returns_const = pnl_change / initial_capital (where initial_capital = 1,000,000,000)
    daily_pnl_change = daily_equity.diff().fillna(0.0)
    daily_returns_const = daily_pnl_change / result.initial_capital

    # === PERFORMANCE METRICS ===
    cumulative_return = total_profit_pct

    # CAGR (calculated using trading days / 252 as years, with initial capital as base)
    if len(daily_equity) > 0:
        years = len(daily_equity) / 252.0
        if years > 0 and net_equity > 0:
            cagr = (net_equity / result.initial_capital) ** (1 / years) - 1
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

    # Sharpe Ratio (annualized using constant returns and population standard deviation ddof=0)
    if len(daily_returns_const) > 1 and daily_returns_const.std(ddof=0) > 0:
        sharpe = daily_returns_const.mean() / daily_returns_const.std(ddof=0) * np.sqrt(252)
    else:
        sharpe = 0.0

    # Sortino Ratio (annualized using rolling returns and standard downside deviation)
    if len(daily_returns_rolling) > 1:
        downside_dev = np.sqrt(np.mean(np.minimum(0, daily_returns_rolling) ** 2))
        if downside_dev > 0:
            sortino = daily_returns_rolling.mean() / downside_dev * np.sqrt(252)
        else:
            sortino = float('inf') if daily_returns_rolling.mean() > 0 else 0.0
    else:
        sortino = 0.0

    # Max Drawdown (calculated on the daily equity series)
    rolling_max = daily_equity.cummax()
    drawdown = (daily_equity - rolling_max) / rolling_max
    max_drawdown = drawdown.min() * 100

    # Calmar Ratio
    calmar = cagr / abs(max_drawdown / 100) if max_drawdown != 0 else 0.0

    # Payoff Ratio
    payoff = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    # Volatility (annualized std of rolling returns using ddof=1)
    if len(daily_returns_rolling) > 1:
        volatility = daily_returns_rolling.std(ddof=1) * np.sqrt(252)
    else:
        volatility = 0.0

    # === ADVANCED METRICS ===

    # Recovery Factor (total net profit divided by absolute max drawdown cash value)
    if max_drawdown != 0:
        max_dd_abs = abs(drawdown.min()) * result.initial_capital
        net_profit = net_equity - result.initial_capital
        recovery_factor = net_profit / max_dd_abs if max_dd_abs > 0 else 0.0
    else:
        recovery_factor = 0.0

    # Kelly Criterion
    if n_completed > 0:
        win_prob = len(wins) / n_completed
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
        if win_loss_ratio > 0:
            kelly = win_prob - (1 - win_prob) / win_loss_ratio
        else:
            kelly = win_prob
    else:
        kelly = 0.0

    # Omega Ratio (threshold = 0) on rolling returns
    if len(daily_returns_rolling) > 0:
        gains = daily_returns_rolling[daily_returns_rolling > 0].sum()
        losses_sum = abs(daily_returns_rolling[daily_returns_rolling < 0].sum())
        omega = gains / losses_sum if losses_sum > 0 else float('inf')
    else:
        omega = 0.0

    # Ulcer Index on daily drawdown (as ratio)
    if len(daily_equity) > 0:
        ulcer_index = np.sqrt((drawdown ** 2).mean())
    else:
        ulcer_index = 0.0

    # VaR (5%, parametric on rolling returns with ddof=1)
    if len(daily_returns_rolling) > 1:
        var_95 = (daily_returns_rolling.mean() - 1.6448536269514722 * daily_returns_rolling.std(ddof=1)) * 100
    else:
        var_95 = 0.0

    # CVaR (historical Expected Shortfall on rolling returns)
    if len(daily_returns_rolling) > 1:
        hist_var_threshold = np.percentile(daily_returns_rolling, 5)
        cvar = daily_returns_rolling[daily_returns_rolling <= hist_var_threshold].mean() * 100
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
    print("  +--- Transaction Analysis ----------------------------------+")
    print(f"  |  Initial Capital     {m['initial_capital']:>20,.0f} d       |")
    print(f"  |  Net Equity          {m['net_equity']:>20,.0f} d       |")
    print(f"  |  Total Profit        {m['total_profit_pct']:>+19.2f} %       |")
    print(f"  |  Total Fees          {m['total_fees_pct']:>+19.2f} %       |")
    print(f"  |  Total Trades        {m['total_trades']:>20}         |")
    print(f"  |  Largest Win         {m['largest_win_pct']:>+19.2f} %       |")
    print(f"  |  Largest Loss        {m['largest_loss_pct']:>+19.2f} %       |")
    print(f"  |  Avg Win             {m['avg_win_pct']:>+19.2f} %       |")
    print(f"  |  Avg Loss            {m['avg_loss_pct']:>+19.2f} %       |")
    print(f"  |  Unrealized PnL      {m['unrealized_pnl']:>20,.0f} d       |")
    print("  +-----------------------------------------------------------+")

    # Performance Metrics
    print()
    print("  +--- Performance Metrics -----------------------------------+")
    print(f"  |  Cumulative Return   {m['cumulative_return_pct']:>+19.2f} %       |")
    print(f"  |  CAGR                {m['cagr_pct']:>+19.2f} %       |")
    print(f"  |  Win Rate            {m['win_rate_pct']:>+19.2f} %       |")
    print(f"  |  Profit Factor       {m['profit_factor']:>20.2f}         |")
    print(f"  |  Sharpe Ratio        {m['sharpe_ratio']:>20.2f}         |")
    print(f"  |  Sortino Ratio       {m['sortino_ratio']:>20.2f}         |")
    print(f"  |  Calmar Ratio        {m['calmar_ratio']:>20.2f}         |")
    print(f"  |  Payoff Ratio        {m['payoff_ratio']:>20.2f}         |")
    print(f"  |  Volatility          {m['volatility']:>20.2f}         |")
    print(f"  |  Max Drawdown        {m['max_drawdown_pct']:>+19.2f} %       |")
    print("  +-----------------------------------------------------------+")

    # Advanced Metrics
    print()
    print("  +--- Advanced Metrics --------------------------------------+")
    print(f"  |  Recovery Factor     {m['recovery_factor']:>20.2f}         |")
    print(f"  |  Kelly Criterion     {m['kelly_criterion_pct']:>+19.2f} %       |")
    print(f"  |  Omega Ratio         {m['omega_ratio']:>20.2f}         |")
    print(f"  |  Ulcer Index         {m['ulcer_index']:>20.2f}         |")
    print(f"  |  VaR                 {m['var_95_pct']:>+19.2f} %       |")
    print(f"  |  CVaR                {m['cvar_95_pct']:>+19.2f} %       |")
    print("  +-----------------------------------------------------------+")
    print()

def validate_metrics(metrics: dict, min_sharpe: float = 0.5, max_mdd: float = 20.0, min_trades: int = 10) -> bool:
    """
    Kiểm tra xem các chỉ số hiệu suất có vượt qua bộ lọc Failed Metrics của web hay không.
    Trả về True nếu pass, ném ngoại lệ ValueError nếu fail.
    """
    import logging
    logger = logging.getLogger("xno_sdk.validator")
    
    errors = []
    
    if metrics['sharpe_ratio'] < min_sharpe:
        errors.append(f"Sharpe Ratio quá thấp ({metrics['sharpe_ratio']:.2f} < {min_sharpe})")
        
    if abs(metrics['max_drawdown_pct']) > max_mdd:
        errors.append(f"Max Drawdown quá cao ({abs(metrics['max_drawdown_pct']):.2f}% > {max_mdd}%)")
        
    if metrics['total_trades'] < min_trades:
        errors.append(f"Số lượng giao dịch quá ít ({metrics['total_trades']} < {min_trades})")
        
    if errors:
        error_msg = "FAILED METRICS - Chiến lược bị loại do không đạt tiêu chuẩn XNOQuant:\n  - " + "\n  - ".join(errors)
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    logger.info("PASSED METRICS - Chiến lược đạt chuẩn hiệu suất cơ bản.")
    return True
