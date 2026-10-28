import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

"""
Portfolio Manager
=================
Stores accepted strategies (code, equity curve, positions) and writes portfolio_summary.json.

Nothing is rejected here: every strategy passed to `evaluate_and_add` is stored. Correlation to
the existing strategies is measured and reported (warning above `MAX_CORRELATION`), never used
to refuse a strategy. HMM validation outcomes passed in `metrics` are stored as information.
"""

import json
import os
import time
from datetime import datetime
from typing import Optional
from pathlib import Path

import numpy as np
import pandas as pd
from utilities.AppConfig import PROJECT_ROOT

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)


# Correlation above this prints a warning only.
MAX_CORRELATION = 0.5


class PortfolioManager:
    """
    Manages the portfolio of accepted strategies.
    
    Parameters
    ----------
    results_dir : str
        Directory to save results.
    """
    
    def __init__(self, results_dir: str = None, max_correlation: float = None):
        if results_dir is None:
            results_dir = os.path.join(PROJECT_ROOT, "results")
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.max_correlation = max_correlation or MAX_CORRELATION
        
        self.strategies: list[dict] = []
        self._equity_curves: list[pd.Series] = []
        self._position_series: list[pd.Series] = []
        
        # Load existing if resuming
        self._load_existing()
    
    def _load_existing(self):
        """Load previously saved strategies, equity curves, and position series."""
        summary_path = self.results_dir / "portfolio_summary.json"
        if summary_path.exists():
            try:
                with open(summary_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                self.strategies = saved.get('strategies', [])
                
                # Load equity and position curves for correlation checks
                for s in self.strategies:
                    eq_path = self.results_dir / f"{s['name']}_{s['timeframe']}_equity.csv"
                    if eq_path.exists():
                        eq = pd.read_csv(eq_path, index_col=0, parse_dates=True).squeeze()
                        self._equity_curves.append(eq)
                    else:
                        # print(f"  ⚠️ Missing equity curve: {eq_path.name}")
                        self._equity_curves.append(None)
                        
                    pos_path = self.results_dir / f"{s['name']}_{s['timeframe']}_positions.csv"
                    if pos_path.exists():
                        pos = pd.read_csv(pos_path, index_col=0, parse_dates=True).squeeze()
                        self._position_series.append(pos)
                    else:
                        self._position_series.append(None)
                
                print(f"[Portfolio] Loaded {len(self.strategies)} strategies, "
                      f"{len([e for e in self._equity_curves if e is not None])} equity curves, "
                      f"{len([p for p in self._position_series if p is not None])} position curves")
            except Exception as e:
                print(f"[Portfolio] Load error: {e}")
    
    def compute_max_correlation(self, new_equity: pd.Series) -> float:
        """
        Compute maximum correlation between new equity curve and all existing.
        
        Returns
        -------
        float
            Maximum absolute correlation (0 if no existing strategies).
        """
        valid_curves = [e for e in self._equity_curves if e is not None]
        if not valid_curves:
            return 0.0
        
        # Compute daily returns
        new_returns = new_equity.pct_change().dropna()
        if len(new_returns) < 10:
            return 0.0
        
        max_corr = 0.0
        for existing_equity in valid_curves:
            existing_returns = existing_equity.pct_change().dropna()
            
            # Align indices
            common_idx = new_returns.index.intersection(existing_returns.index)
            if len(common_idx) < 10:
                continue
            
            corr = abs(new_returns.loc[common_idx].corr(existing_returns.loc[common_idx]))
            if not np.isnan(corr):
                max_corr = max(max_corr, corr)
        
        return max_corr

    def compute_max_position_correlation(self, new_positions: pd.Series) -> float:
        """
        Compute maximum correlation between new position series and all existing.
        
        Returns
        -------
        float
            Maximum absolute correlation (0 if no existing strategies).
        """
        valid_positions = [p for p in self._position_series if p is not None]
        if not valid_positions or new_positions is None:
            return 0.0
        
        max_corr = 0.0
        for existing_positions in valid_positions:
            # Align indices
            common_idx = new_positions.index.intersection(existing_positions.index)
            if len(common_idx) < 10:
                continue
            
            corr = abs(new_positions.loc[common_idx].corr(existing_positions.loc[common_idx]))
            if not np.isnan(corr):
                max_corr = max(max_corr, corr)
        
        return max_corr
    
    def evaluate_and_add(
        self,
        name: str,
        timeframe: str,
        family: str,
        description: str,
        code: str,
        params: dict,
        metrics: dict,
        equity_curve: pd.Series,
        positions: pd.Series = None,
    ) -> tuple[bool, str]:
        """
        Add a strategy to the portfolio and report its correlation to the existing ones.

        Never rejects: a correlation above `max_correlation` only prints a warning. Optional
        `metrics` keys `hmm_passed`, `hmm_tier_failed`, `hmm_reason` are stored with the entry.

        Returns
        -------
        (accepted, reason)
        """
        # ── Check correlation ──
        max_corr_returns = self.compute_max_correlation(equity_curve)
        max_corr_positions = self.compute_max_position_correlation(positions)
        
        if max_corr_returns > self.max_correlation:
            reason = f"WARNING (return correlation): max_corr_returns={max_corr_returns:.2f} > {self.max_correlation}"
            print(f"  ⚠️ {reason}")
            
        if max_corr_positions > self.max_correlation:
            reason = f"WARNING (position correlation): max_corr_positions={max_corr_positions:.2f} > {self.max_correlation}"
            print(f"  ⚠️ {reason}")
        
        # ── Accept! ──
        strategy_entry = {
            'name': name,
            'timeframe': timeframe,
            'family': family,
            'description': description,
            'params': params,
            'metrics': {
                'sharpe_ratio': round(metrics.get('sharpe_ratio', 0), 3),
                'cagr': round(metrics.get('cagr', 0), 4),
                'max_drawdown_pct': round(metrics.get('max_drawdown_pct', 0), 2),
                'profit_factor': round(metrics.get('profit_factor', 0), 3),
                'calmar_ratio': round(metrics.get('calmar_ratio', 0), 3),
                'total_trades': metrics.get('total_trades', 0),
                'win_rate': round(metrics.get('win_rate', 0), 2),
            },
            'hmm': {
                'passed': metrics.get('hmm_passed'),
                'tier_failed': metrics.get('hmm_tier_failed'),
                'reason': metrics.get('hmm_reason'),
            },
            'max_correlation_returns': round(max_corr_returns, 3),
            'max_correlation_positions': round(max_corr_positions, 3),
            'accepted_at': datetime.now().isoformat(),
        }
        
        self.strategies.append(strategy_entry)
        self._equity_curves.append(equity_curve)
        self._position_series.append(positions)
        
        # Save code
        code_path = self.results_dir / f"{name}_{timeframe}.py"
        with open(code_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # Save equity curve for future correlation checks
        eq_path = self.results_dir / f"{name}_{timeframe}_equity.csv"
        equity_curve.to_csv(eq_path)
        
        # Save positions series for future correlation checks
        if positions is not None:
            pos_path = self.results_dir / f"{name}_{timeframe}_positions.csv"
            positions.to_csv(pos_path)
        
        # Save portfolio summary
        self._save_summary()
        
        max_c = max(max_corr_returns, max_corr_positions)
        reason = (f"ACCEPTED #{len(self.strategies)} | "
                  f"Sharpe={metrics.get('sharpe_ratio', 0):.2f} "
                  f"CAGR={metrics.get('cagr', 0)*100:.1f}% "
                  f"MDD={metrics.get('max_drawdown_pct', 0):.1f}% "
                  f"Corr={max_c:.2f} (Ret={max_corr_returns:.2f}, Pos={max_corr_positions:.2f})")
        return True, reason
    
    def _save_summary(self):
        """Save portfolio summary to JSON."""
        summary = {
            'total_accepted': len(self.strategies),
            'last_updated': datetime.now().isoformat(),
            'strategies': self.strategies,
        }
        path = self.results_dir / "portfolio_summary.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, cls=NpEncoder)
    
    def list(self) -> list[dict]:
        """Return list of strategy summaries (for prompt)."""
        return [
            {
                'name': s['name'],
                'timeframe': s['timeframe'],
                'family': s['family'],
                'description': s['description'],
            }
            for s in self.strategies
        ]
    
    def print_summary(self):
        """Print portfolio summary table."""
        if not self.strategies:
            print("[Portfolio] Empty — no strategies accepted yet")
            return
        
        print(f"\n{'='*80}")
        print(f"  PORTFOLIO: {len(self.strategies)} strategies")
        print(f"{'='*80}")
        print(f"{'#':>3} {'Name':<25} {'TF':>4} {'Family':<18} {'Sharpe':>7} {'CAGR%':>7} {'MDD%':>7} {'PF':>6} {'Corr':>6}")
        print(f"{'-'*80}")
        
        for i, s in enumerate(self.strategies, 1):
            m = s['metrics']
            max_c = s.get('max_correlation')
            if max_c is None:
                max_c = max(s.get('max_correlation_returns', 0.0), s.get('max_correlation_positions', 0.0))
            print(f"{i:3d} {s['name']:<25} {s['timeframe']:>4} {s['family']:<18} "
                  f"{m['sharpe_ratio']:7.2f} {m['cagr']*100:6.1f}% "
                  f"{m['max_drawdown_pct']:6.1f}% {m['profit_factor']:6.2f} "
                  f"{max_c:6.2f}")
        
        print(f"{'='*80}\n")
