"""
Generic Strategy Optimizer
==========================
Powerful optimizer that works with any BaseStrategy subclass.
Uses Optuna for intelligent hyperparameter search.

Supported methods:
    - 'bayesian' (default): TPE sampler — smart, converges fast
    - 'grid': Exhaustive grid search — tries all combinations
    - 'random': Random sampling — good baseline

Usage:
    from backtest.optimizer import Optimizer, IntParam, FloatParam

    optimizer = Optimizer(
        strategy_class=SMACrossover,
        param_space={
            'fast_period': IntParam(3, 30),
            'slow_period': IntParam(10, 100, step=5),
        },
        data=data,
        engine_config={'max_contracts': 1},
        objective='sharpe_ratio',
        method='bayesian',
        n_trials=200,
        n_jobs=-1,
        param_constraints=lambda p: p['fast_period'] < p['slow_period'],
    )
    result = optimizer.run()
"""

from dataclasses import dataclass
from typing import Type, Dict, List, Optional, Union, Callable, Any
import time as time_module
import warnings
import os

import pandas as pd
import numpy as np

try:
    import optuna
    from optuna.samplers import TPESampler, GridSampler, RandomSampler
    # Suppress Optuna's verbose trial-by-trial logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    raise ImportError(
        "optuna is required for the optimizer. "
        "Install with: pip install optuna"
    )

from backtest.engine import XNOBacktestEngine, BacktestResult
from backtest.strategy import SimpleAlgorithm
from backtest import reporting


# ═══════════════════════════════════════════════════════════════════════
# Parameter Space Definitions
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class IntParam:
    """Integer parameter with range [low, high] and optional step."""
    low: int
    high: int
    step: int = 1


@dataclass
class FloatParam:
    """Float parameter with range [low, high] and optional step."""
    low: float
    high: float
    step: Optional[float] = None  # None = continuous


@dataclass
class CategoricalParam:
    """Categorical parameter with discrete choices."""
    choices: list


# ═══════════════════════════════════════════════════════════════════════
# Optimization Result
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class OptimizationResult:
    """
    Complete results from an optimization run.

    Attributes
    ----------
    study : optuna.Study
        The Optuna study object (for advanced analysis/visualization).
    results_df : pd.DataFrame
        All completed trials as a DataFrame, sorted by objective.
    best_params : dict
        Best parameter combination found.
    best_value : float or dict
        Best objective value(s).
    best_result : BacktestResult
        Full backtest result using best parameters.
    elapsed_seconds : float
        Total wall-clock time for optimization.
    n_completed : int
        Number of completed (non-pruned) trials.
    n_pruned : int
        Number of pruned trials (invalid constraints / errors).
    """
    study: Any
    results_df: pd.DataFrame
    best_params: dict
    best_value: Union[float, dict]
    best_result: BacktestResult
    elapsed_seconds: float
    n_completed: int
    n_pruned: int


# ═══════════════════════════════════════════════════════════════════════
# Optimizer
# ═══════════════════════════════════════════════════════════════════════

class Optimizer:
    """
    Generic strategy parameter optimizer using Optuna.

    Parameters
    ----------
    strategy_class : Type[SimpleAlgorithm]
        Strategy class to optimize (must accept param names as __init__ kwargs).
    param_space : dict
        Search space. Keys = strategy __init__ kwarg names.
        Values = IntParam, FloatParam, or CategoricalParam.
    data : pd.DataFrame
        Prepared DataFrame from data_pipeline.prepare().
    engine_config : dict, optional
        Override XNOBacktestEngine parameters (initial_capital,
        margin_rate, fee_per_contract).
    objective : str or list[str]
        Metric(s) to optimize. Must match keys from reporting.compute_metrics().
        Examples: 'sharpe_ratio', 'total_pnl', 'profit_factor'.
    direction : str or list[str]
        'maximize' or 'minimize' per objective.
    method : str
        'bayesian' (TPE — default), 'grid', or 'random'.
    n_trials : int
        Number of trials. Ignored for grid search (runs all combos).
    n_jobs : int
        Parallel workers. -1 = all CPU cores. Default 1.
    param_constraints : callable, optional
        Takes params dict, returns True if valid. Invalid combos are skipped.
    seed : int
        Random seed for reproducibility.
    verbose : bool
        Print progress and results.
    """

    VALID_METHODS = ('grid', 'random', 'bayesian')

    def __init__(
        self,
        strategy_class: Type[SimpleAlgorithm],
        param_space: Dict[str, Union[IntParam, FloatParam, CategoricalParam]],
        data: pd.DataFrame,
        engine_config: Optional[dict] = None,
        objective: Union[str, List[str]] = 'sharpe_ratio',
        direction: Union[str, List[str]] = 'maximize',
        method: str = 'bayesian',
        n_trials: int = 100,
        n_jobs: int = 1,
        param_constraints: Optional[Callable] = None,
        seed: int = 42,
        verbose: bool = True,
    ):
        if method not in self.VALID_METHODS:
            raise ValueError(
                f"method must be one of {self.VALID_METHODS}, got '{method}'"
            )

        self.strategy_class = strategy_class
        self.param_space = param_space
        self.data = data
        self.engine_config = engine_config or {}
        self.method = method
        self.n_trials = n_trials
        self.param_constraints = param_constraints
        self.seed = seed
        self.verbose = verbose

        # Normalize objective / direction to lists
        if isinstance(objective, str):
            self.objectives = [objective]
        else:
            self.objectives = list(objective)

        if isinstance(direction, str):
            self.directions = [direction] * len(self.objectives)
        else:
            self.directions = list(direction)

        self.is_multi_objective = len(self.objectives) > 1

        # Validate
        for d in self.directions:
            if d not in ('maximize', 'minimize'):
                raise ValueError(
                    f"direction must be 'maximize' or 'minimize', got '{d}'"
                )
        if len(self.objectives) != len(self.directions):
            raise ValueError(
                f"objectives ({len(self.objectives)}) and "
                f"directions ({len(self.directions)}) must have same length"
            )

        # Resolve n_jobs
        if n_jobs == -1:
            self.n_jobs = os.cpu_count() or 1
        else:
            self.n_jobs = max(1, n_jobs)

    # ── Main Entry Point ─────────────────────────────────────────────

    def run(self) -> OptimizationResult:
        """
        Run the optimization.

        Returns
        -------
        OptimizationResult
            Complete optimization results including best params,
            all trials DataFrame, and best backtest result.
        """
        start_time = time_module.time()

        # Create sampler
        sampler = self._create_sampler()

        # Create Optuna study
        if self.is_multi_objective:
            study = optuna.create_study(
                directions=self.directions,
                sampler=sampler,
                study_name=f"opt_{self.strategy_class.__name__}",
            )
        else:
            study = optuna.create_study(
                direction=self.directions[0],
                sampler=sampler,
                study_name=f"opt_{self.strategy_class.__name__}",
            )

        # Determine trial count
        if self.method == 'grid':
            n_trials = self._count_grid_combos()
        else:
            n_trials = self.n_trials

        # Print header
        if self.verbose:
            self._print_header(n_trials)

        # Build objective function
        objective_fn = self._create_objective()

        # Run optimization
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            study.optimize(
                objective_fn,
                n_trials=n_trials,
                n_jobs=self.n_jobs,
                show_progress_bar=self.verbose,
            )

        elapsed = time_module.time() - start_time

        # Count trial states
        n_completed = sum(
            1 for t in study.trials
            if t.state == optuna.trial.TrialState.COMPLETE
        )
        n_pruned = sum(
            1 for t in study.trials
            if t.state == optuna.trial.TrialState.PRUNED
        )

        # Build results DataFrame
        results_df = self._build_results_df(study)

        # Extract best params
        if self.is_multi_objective:
            best_trials = study.best_trials
            if best_trials:
                best_params = best_trials[0].params
                best_value = {
                    obj: val
                    for obj, val in zip(self.objectives, best_trials[0].values)
                }
            else:
                best_params = {}
                best_value = {}
        else:
            best_params = study.best_params
            best_value = study.best_value

        # Re-run full backtest with best params
        best_result = self._run_backtest(best_params)

        result = OptimizationResult(
            study=study,
            results_df=results_df,
            best_params=best_params,
            best_value=best_value,
            best_result=best_result,
            elapsed_seconds=elapsed,
            n_completed=n_completed,
            n_pruned=n_pruned,
        )

        if self.verbose:
            self.print_results(result)

        return result

    # ── Internal: Sampler & Objective ────────────────────────────────

    def _create_sampler(self):
        """Create the Optuna sampler based on search method."""
        if self.method == 'grid':
            search_space = {}
            for name, param in self.param_space.items():
                if isinstance(param, IntParam):
                    search_space[name] = list(
                        range(param.low, param.high + 1, param.step)
                    )
                elif isinstance(param, FloatParam):
                    if param.step is None:
                        raise ValueError(
                            f"Grid search requires 'step' for FloatParam "
                            f"'{name}'. Set step or use method='bayesian'."
                        )
                    vals = np.arange(
                        param.low,
                        param.high + param.step * 0.5,
                        param.step,
                    )
                    search_space[name] = [round(float(v), 10) for v in vals]
                elif isinstance(param, CategoricalParam):
                    search_space[name] = param.choices
            return GridSampler(search_space, seed=self.seed)

        elif self.method == 'random':
            return RandomSampler(seed=self.seed)

        else:  # bayesian
            return TPESampler(
                seed=self.seed,
                n_startup_trials=min(10, max(1, self.n_trials // 5)),
                multivariate=True,
            )

    def _count_grid_combos(self) -> int:
        """Count total grid search combinations (before constraints)."""
        total = 1
        for param in self.param_space.values():
            if isinstance(param, IntParam):
                total *= len(range(param.low, param.high + 1, param.step))
            elif isinstance(param, FloatParam) and param.step is not None:
                total *= len(np.arange(
                    param.low, param.high + param.step * 0.5, param.step,
                ))
            elif isinstance(param, CategoricalParam):
                total *= len(param.choices)
        return total

    def _create_objective(self):
        """Build the Optuna objective function as a closure."""
        # Capture references (avoids self in closure for thread safety)
        strategy_cls = self.strategy_class
        param_space = self.param_space
        data = self.data
        engine_cfg = self.engine_config
        objectives = self.objectives
        constraints = self.param_constraints
        is_multi = self.is_multi_objective

        def objective(trial):
            # ① Sample parameters
            params = {}
            for name, space in param_space.items():
                if isinstance(space, IntParam):
                    params[name] = trial.suggest_int(
                        name, space.low, space.high, step=space.step,
                    )
                elif isinstance(space, FloatParam):
                    if space.step is not None:
                        params[name] = trial.suggest_float(
                            name, space.low, space.high, step=space.step,
                        )
                    else:
                        params[name] = trial.suggest_float(
                            name, space.low, space.high,
                        )
                elif isinstance(space, CategoricalParam):
                    params[name] = trial.suggest_categorical(
                        name, space.choices,
                    )

            # ② Check constraints
            if constraints is not None and not constraints(params):
                raise optuna.TrialPruned()

            # ③ Run backtest
            try:
                strategy = strategy_cls(**params)
                engine = XNOBacktestEngine(**engine_cfg)
                result = engine.run(strategy, data)
                metrics = reporting.compute_metrics(result)
            except Exception:
                raise optuna.TrialPruned()

            # ④ Store all metrics as user attributes for later analysis
            for key, val in metrics.items():
                if isinstance(val, (int, float, np.integer, np.floating)):
                    trial.set_user_attr(key, float(val))

            # ⑤ Return objective value(s)
            if is_multi:
                return tuple(metrics.get(obj, 0.0) for obj in objectives)
            return metrics.get(objectives[0], 0.0)

        return objective

    def _run_backtest(self, params: dict) -> BacktestResult:
        """Run a single backtest with given parameters."""
        strategy = self.strategy_class(**params)
        engine = XNOBacktestEngine(**self.engine_config)
        return engine.run(strategy, self.data)

    def _build_results_df(self, study) -> pd.DataFrame:
        """Convert all completed trials to a sorted DataFrame."""
        records = []
        for trial in study.trials:
            if trial.state != optuna.trial.TrialState.COMPLETE:
                continue

            row = {'trial': trial.number}
            row.update(trial.params)

            # Objective values
            if self.is_multi_objective:
                for name, val in zip(self.objectives, trial.values):
                    row[name] = val
            else:
                row[self.objectives[0]] = trial.value

            # All stored metrics
            row.update(trial.user_attrs)
            records.append(row)

        df = pd.DataFrame(records)

        # Sort by primary objective
        if not df.empty and not self.is_multi_objective:
            ascending = self.directions[0] == 'minimize'
            df = df.sort_values(
                self.objectives[0], ascending=ascending,
            ).reset_index(drop=True)

        return df

    # ── Output & Display ─────────────────────────────────────────────

    def _print_header(self, n_trials: int) -> None:
        """Print optimization header banner."""
        method_label = {
            'bayesian': 'BAYESIAN (TPE)',
            'grid': 'GRID SEARCH',
            'random': 'RANDOM SEARCH',
        }
        print(f"\n{'=' * 60}")
        print(f"  OPTIMIZER — {self.strategy_class.__name__}")
        print(f"{'=' * 60}")
        print(f"  Method:     {method_label[self.method]}")
        print(f"  Objective:  {', '.join(self.objectives)}")
        print(f"  Trials:     {n_trials}")
        print(f"  Parallel:   {self.n_jobs} job{'s' if self.n_jobs > 1 else ''}")
        print(f"  Params:     {list(self.param_space.keys())}")
        print(f"{'=' * 60}\n")

    def print_results(
        self, result: OptimizationResult, top_n: int = 20,
    ) -> None:
        """Print formatted optimization results table."""
        df = result.results_df
        if df.empty:
            print("\nNo completed trials.")
            return

        method_label = {
            'bayesian': 'BAYESIAN (TPE)',
            'grid': 'GRID SEARCH',
            'random': 'RANDOM SEARCH',
        }

        print(f"\n{'=' * 90}")
        print(f"  OPTIMIZATION COMPLETE — {self.strategy_class.__name__}")
        print(f"{'=' * 90}")
        print(f"  Method:       {method_label[self.method]}")
        print(f"  Completed:    {result.n_completed} trials in "
              f"{result.elapsed_seconds:.1f}s "
              f"({result.n_pruned} pruned)")
        print(f"  Best params:  {result.best_params}")

        if isinstance(result.best_value, dict):
            for obj, val in result.best_value.items():
                print(f"  Best {obj}: {val:.4f}")
        else:
            print(f"  Best {self.objectives[0]}: {result.best_value:.4f}")

        # Build display columns
        param_names = list(self.param_space.keys())
        metric_display = [
            c for c in [
                'total_pnl', 'total_return_pct', 'sharpe_ratio',
                'cagr', 'calmar_ratio',
                'win_rate', 'profit_factor', 'max_drawdown_pct',
                'total_trades',
            ]
            if c in df.columns
        ]
        display_cols = param_names + metric_display

        n_show = min(top_n, len(df))
        print(f"\n  TOP {n_show} RESULTS:")
        print(f"  {'-' * 88}")

        # Header row
        header = f"  {'#':>4}"
        for col in display_cols:
            header += f"  {self._short_name(col):>10}"
        print(header)
        print(f"  {'-' * 88}")

        # Data rows
        for rank, (_, row) in enumerate(df.head(n_show).iterrows(), 1):
            line = f"  {rank:>4}"
            for col in display_cols:
                val = row.get(col, '')
                if isinstance(val, (int, np.integer)):
                    line += f"  {val:>10}"
                elif isinstance(val, (float, np.floating)):
                    if abs(val) >= 100_000:
                        line += f"  {val:>10,.0f}"
                    else:
                        line += f"  {val:>10.2f}"
                else:
                    line += f"  {str(val):>10}"
            print(line)

        print(f"  {'=' * 88}")

        # Full backtest summary of the best
        print(f"\n  BEST PARAMS — FULL BACKTEST:")
        reporting.print_summary(result.best_result)

    @staticmethod
    def _short_name(col: str) -> str:
        """Abbreviate column names for compact table display."""
        _map = {
            'total_pnl': 'PnL',
            'total_return_pct': 'Ret%',
            'sharpe_ratio': 'Sharpe',
            'cagr': 'CAGR',
            'calmar_ratio': 'Calmar',
            'win_rate': 'WinR%',
            'profit_factor': 'PF',
            'max_drawdown_pct': 'MaxDD%',
            'total_trades': 'Trades',
            'trades_per_day': 'T/Day',
            'max_consecutive_losses': 'MaxCLoss',
            'avg_trade': 'AvgTrade',
        }
        return _map.get(col, col[:10])

    # ── Visualization ────────────────────────────────────────────────

    def plot_optimization_history(
        self, result: OptimizationResult,
    ) -> None:
        """Plot objective value across trials (scatter + running best)."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib required for plotting.")
            return

        df = result.results_df
        if df.empty:
            return

        obj = self.objectives[0]
        is_max = self.directions[0] == 'maximize'

        # Sort by trial execution order for history plot
        df_hist = df.sort_values('trial').copy()

        fig, ax = plt.subplots(figsize=(12, 5))

        # Scatter all trials
        ax.scatter(
            df_hist['trial'], df_hist[obj],
            alpha=0.35, s=15, color='#64B5F6',
            label='Trials', zorder=2,
        )

        # Running best line
        best_so_far = (
            df_hist[obj].expanding().max() if is_max
            else df_hist[obj].expanding().min()
        )
        ax.plot(
            df_hist['trial'].values, best_so_far.values,
            color='#E53935', linewidth=2,
            label='Best so far', zorder=3,
        )

        ax.set_xlabel('Trial #')
        ax.set_ylabel(obj)
        ax.set_title(
            f'Optimization History — {self.strategy_class.__name__}',
            fontsize=13, fontweight='bold',
        )
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig('optimization_history.png', dpi=150, bbox_inches='tight')
        plt.show()
        print("Saved optimization_history.png")

    def plot_param_importances(
        self, result: OptimizationResult,
    ) -> None:
        """Plot parameter importance (fANOVA-based)."""
        try:
            from optuna.visualization.matplotlib import plot_param_importances
            import matplotlib.pyplot as plt
            plot_param_importances(result.study)
            plt.title(
                f'Parameter Importances — {self.strategy_class.__name__}',
                fontweight='bold',
            )
            plt.tight_layout()
            plt.savefig(
                'param_importances.png', dpi=150, bbox_inches='tight',
            )
            plt.show()
            print("Saved param_importances.png")
        except Exception as e:
            print(f"Could not plot param importances: {e}")

    def plot_contour(
        self,
        result: OptimizationResult,
        params: Optional[list] = None,
    ) -> None:
        """Plot 2D contour of objective over parameter pairs."""
        try:
            from optuna.visualization.matplotlib import plot_contour
            import matplotlib.pyplot as plt
            plot_contour(result.study, params=params)
            plt.suptitle(
                f'Contour — {self.strategy_class.__name__}',
                fontweight='bold',
            )
            plt.tight_layout()
            plt.savefig('contour_plot.png', dpi=150, bbox_inches='tight')
            plt.show()
            print("Saved contour_plot.png")
        except Exception as e:
            print(f"Could not plot contour: {e}")

    def plot_slice(self, result: OptimizationResult) -> None:
        """Plot slice: objective vs each individual parameter."""
        try:
            from optuna.visualization.matplotlib import plot_slice
            import matplotlib.pyplot as plt
            plot_slice(result.study)
            plt.suptitle(
                f'Slice Plot — {self.strategy_class.__name__}',
                fontweight='bold',
            )
            plt.tight_layout()
            plt.savefig('slice_plot.png', dpi=150, bbox_inches='tight')
            plt.show()
            print("Saved slice_plot.png")
        except Exception as e:
            print(f"Could not plot slice: {e}")

    # ── Export ────────────────────────────────────────────────────────

    def export_results(
        self, result: OptimizationResult, filepath: str,
    ) -> None:
        """Export all trial results to CSV."""
        result.results_df.to_csv(filepath, index=False)
        print(f"Exported {len(result.results_df)} trials to {filepath}")
