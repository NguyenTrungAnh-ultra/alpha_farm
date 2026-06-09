"""
VN30F1M Intraday Backtest Runner
================================
Entry point for running backtests and parameter optimization.

Usage:
    python run_backtest.py                                    # Default SMA
    python run_backtest.py --optimize                         # Bayesian optimize
    python run_backtest.py --optimize --method grid           # Grid search
    python run_backtest.py --optimize --objective total_pnl   # Max PnL
    python run_backtest.py --optimize --jobs -1               # All CPU cores
"""

import argparse

from backtest import data_pipeline as dp
from backtest.engine import BacktestEngine
from backtest import reporting
from backtest.optimizer import Optimizer, IntParam, FloatParam
from strategies.sma_crossover import SMACrossover


def run_single(data, fast_period=10, slow_period=30, verbose=True):
    """Run a single backtest with given parameters."""
    engine = BacktestEngine(
        initial_capital=100_000_000,
        commission=4_500,
        slippage=0.1,
        max_contracts=1,
    )
    strategy = SMACrossover(fast_period=fast_period, slow_period=slow_period)
    result = engine.run(data, strategy)

    if verbose:
        print(f"\nStrategy: SMA Crossover (fast={fast_period}, slow={slow_period})")
        reporting.print_summary(result)
        reporting.plot_equity_curve(
            result,
            title=f"SMA Crossover ({fast_period}/{slow_period}) - VN30F1M 5m"
        )
        reporting.export_trades(result.trades, 'trades.csv')

    return result


def optimize(data, method='bayesian', n_trials=200, objective='sharpe_ratio',
             n_jobs=1):
    """
    Optimize SMA Crossover parameters using the generic Optimizer.
    """
    optimizer = Optimizer(
        strategy_class=SMACrossover,
        param_space={
            'fast_period': IntParam(3, 30, step=1),
            'slow_period': IntParam(10, 100, step=5),
        },
        data=data,
        engine_config={
            'initial_capital': 100_000_000,
            'commission': 4_500,
            'slippage': 0.1,
            'max_contracts': 1,
        },
        objective=objective,
        method=method,
        n_trials=n_trials,
        n_jobs=n_jobs,
        param_constraints=lambda p: p['fast_period'] < p['slow_period'],
    )

    result = optimizer.run()

    # Additional plots
    optimizer.plot_optimization_history(result)
    if method == 'bayesian':
        optimizer.plot_param_importances(result)
        optimizer.plot_contour(result)

    # Export
    optimizer.export_results(result, 'optimization_results.csv')

    # Equity curve of best params
    reporting.plot_equity_curve(
        result.best_result,
        title=(
            f"Best: SMA("
            f"{result.best_params.get('fast_period')}/"
            f"{result.best_params.get('slow_period')})"
        ),
    )
    reporting.export_trades(result.best_result.trades, 'trades_best.csv')

    return result


def main():
    parser = argparse.ArgumentParser(description='VN30F1M Intraday Backtest')
    parser.add_argument(
        '--optimize', action='store_true',
        help='Run parameter optimization',
    )
    parser.add_argument(
        '--fast', type=int, default=10,
        help='Fast SMA period (default: 10)',
    )
    parser.add_argument(
        '--slow', type=int, default=30,
        help='Slow SMA period (default: 30)',
    )
    parser.add_argument(
        '--method', type=str, default='bayesian',
        choices=['grid', 'random', 'bayesian'],
        help='Optimization method (default: bayesian)',
    )
    parser.add_argument(
        '--trials', type=int, default=200,
        help='Number of optimization trials (default: 200)',
    )
    parser.add_argument(
        '--objective', type=str, default='sharpe_ratio',
        help='Objective metric to optimize (default: sharpe_ratio)',
    )
    parser.add_argument(
        '--jobs', type=int, default=1,
        help='Parallel jobs, -1=all cores (default: 1)',
    )
    args = parser.parse_args()

    # Load data
    print("Loading and preparing data...")
    data = dp.prepare('data/DNSE_VN30F_5m.csv')
    print(f"Data ready: {len(data):,} bars, "
          f"{data['trading_date'].nunique()} trading days")

    if args.optimize:
        optimize(
            data,
            method=args.method,
            n_trials=args.trials,
            objective=args.objective,
            n_jobs=args.jobs,
        )
    else:
        run_single(data, fast_period=args.fast, slow_period=args.slow)


if __name__ == '__main__':
    main()
