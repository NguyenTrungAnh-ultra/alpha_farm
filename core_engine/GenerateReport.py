"""
GenerateReport
==============
Legacy-compatible reporting module that wraps and maps performance metrics.

Provides backward compatibility for the portfolio manager and pipeline criteria checks 
by translation of the new XNO metrics names to legacy parameter formats.
"""

import pandas as pd
import numpy as np
from core_engine.BacktestEngine import BacktestResult
from core_engine.CalculateMetrics import compute_metrics as xno_compute_metrics, print_report as xno_print_report


def compute_metrics(result: BacktestResult) -> dict:
    """
    Calculate and map strategy metrics for backward compatibility with the pipeline.
    
    Translates standard XNO metrics (like CAGR percentages) to decimal formats
    and adds legacy metrics such as consecutive losses, trades per day, and 
    trade directions (long/short count).

    Parameters
    ----------
    result : BacktestResult
        The backtest results to compute metrics from.

    Returns
    -------
    dict
        A dictionary containing legacy-formatted performance metrics.
    """
    m = xno_compute_metrics(result)
    
    trades = result.trades
    n_trades = len(trades)
    
    # Direction breakdown
    long_trades = sum(1 for t in trades if t.direction > 0)
    short_trades = sum(1 for t in trades if t.direction < 0)
    
    # PnL in VND
    pnls = [t.net_pnl for t in trades] if trades else []
    wins_vnd = [p for p in pnls if p > 0]
    losses_vnd = [p for p in pnls if p <= 0]
    
    return {
        # Core metrics matching portfolio CRITERIA keys
        'total_trades': m['total_trades'],
        'long_trades': long_trades,
        'short_trades': short_trades,
        'win_rate': m['win_rate_pct'],
        'profit_factor': m['profit_factor'],
        'total_pnl': m.get('total_pnl_vnd', sum(pnls)),
        'total_return_pct': m['total_profit_pct'],
        'avg_trade': np.mean(pnls) if pnls else 0,
        'avg_win': np.mean(wins_vnd) if wins_vnd else 0,
        'avg_loss': np.mean(losses_vnd) if losses_vnd else 0,
        'max_drawdown': m['max_drawdown_pct'] / 100 * result.initial_capital if m['max_drawdown_pct'] else 0,
        'max_drawdown_pct': m['max_drawdown_pct'],
        'sharpe_ratio': m['sharpe_ratio'],
        'cagr': m['cagr_pct'] / 100,  # portfolio expects decimal (0.15 = 15%)
        'calmar_ratio': m['calmar_ratio'],
        'max_consecutive_losses': _max_consec_losses(pnls),
        'trades_per_day': n_trades / max(_count_trading_days(result.equity_curve), 1),
        'initial_capital': result.initial_capital,
        'final_equity': result.final_equity,
        
        # Additional XNO metrics (for display)
        'sortino_ratio': m.get('sortino_ratio', 0),
        'total_fees': result.total_fees,
    }


def _max_consec_losses(pnls: list) -> int:
    """
    Calculate the maximum consecutive loss streak in a list of trade PnLs.

    Parameters
    ----------
    pnls : list[float]
        A list of net PnL values.

    Returns
    -------
    int
        The maximum streak of consecutive trades with PnL <= 0.
    """
    max_streak = 0
    current = 0
    for p in pnls:
        if p <= 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def _count_trading_days(equity: pd.Series) -> int:
    """
    Count the number of unique calendar trading days in the equity curve.

    Parameters
    ----------
    equity : pd.Series
        The series of equity values over time.

    Returns
    -------
    int
        Number of unique trading days.
    """
    if len(equity) == 0:
        return 1
    return pd.Series(equity.index.date).nunique()


def print_summary(result: BacktestResult) -> None:
    """
    Print a complete backtest report summary.
    
    Delegates to CalculateMetrics.print_report.

    Parameters
    ----------
    result : BacktestResult
        The backtest result to report.
    """
    xno_print_report(result)


def trades_to_dataframe(trades: list) -> pd.DataFrame:
    """
    Convert a list of TradeRecord objects to a pandas DataFrame.

    Parameters
    ----------
    trades : list[TradeRecord]
        List of completed trade records.

    Returns
    -------
    pd.DataFrame
        DataFrame containing formatted trade logs.
    """
    if not trades:
        return pd.DataFrame()

    return pd.DataFrame([
        {
            'entry_time': t.entry_time,
            'exit_time': t.exit_time,
            'direction': 'LONG' if t.direction > 0 else 'SHORT',
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'contracts': t.contracts,
            'gross_pnl': t.gross_pnl,
            'fee': t.fee,
            'net_pnl': t.net_pnl,
        }
        for t in trades
    ])


def export_trades(trades: list, filepath: str) -> None:
    """
    Export the log of completed trades to a CSV file.

    Parameters
    ----------
    trades : list[TradeRecord]
        List of completed trade records.
    filepath : str
        Target destination path for the exported CSV file.
    """
    df = trades_to_dataframe(trades)
    df.to_csv(filepath, index=False)
    print(f"Exported {len(df)} trades to {filepath}")


def plot_equity_curve(result: BacktestResult, title: str = "Equity Curve") -> None:
    """
    Generate and save an equity curve and drawdown chart.
    
    Plots the daily mark-to-market equity values along with a filled area
    chart representing peak-to-trough drawdowns. Saves the chart to 
    `equity_curve.png`.

    Parameters
    ----------
    result : BacktestResult
        The backtest results to plot.
    title : str, default "Equity Curve"
        The title header of the chart.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Skipping plot.")
        return

    equity = result.equity_curve.dropna()

    if len(equity) == 0:
        print("No equity data to plot.")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), height_ratios=[3, 1],
                                    sharex=True)

    # Equity curve
    ax1.plot(equity.index, equity.values, color='#2196F3', linewidth=1.2)
    ax1.axhline(y=result.initial_capital, color='gray', linestyle='--',
                alpha=0.5, label='Initial Capital')
    ax1.set_title(title, fontsize=14, fontweight='bold')
    ax1.set_ylabel('Equity (VND)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x/1e6:.0f}M'))

    # Drawdown
    rolling_max = equity.cummax()
    drawdown_pct = (equity - rolling_max) / rolling_max * 100
    ax2.fill_between(drawdown_pct.index, drawdown_pct.values, 0,
                     color='#F44336', alpha=0.4)
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Date')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('equity_curve.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("Saved equity_curve.png")
