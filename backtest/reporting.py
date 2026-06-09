"""
Reporting Module (Legacy-compatible)
=====================================
Wraps metrics.py for backward compatibility with the agent pipeline.
Maps new XNO metric names to the legacy names used by portfolio/pipeline.
"""

import pandas as pd
import numpy as np
from backtest.engine import BacktestResult
from backtest.metrics import compute_metrics as xno_compute_metrics, print_report as xno_print_report


def compute_metrics(result: BacktestResult) -> dict:
    """
    Compute metrics and return in the format expected by the agent pipeline/portfolio.
    
    Maps XNO metric names → legacy names used by portfolio CRITERIA checks.
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
    """Calculate max consecutive losses."""
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
    """Count unique trading days in equity curve."""
    if len(equity) == 0:
        return 1
    return pd.Series(equity.index.date).nunique()


def print_summary(result: BacktestResult) -> None:
    """Print summary — delegates to XNO print_report."""
    xno_print_report(result)


def trades_to_dataframe(trades: list) -> pd.DataFrame:
    """Convert list of TradeRecord objects to a DataFrame."""
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
    """Export trade log to CSV."""
    df = trades_to_dataframe(trades)
    df.to_csv(filepath, index=False)
    print(f"Exported {len(df)} trades to {filepath}")


def plot_equity_curve(result: BacktestResult, title: str = "Equity Curve") -> None:
    """Plot equity curve and drawdown chart."""
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
