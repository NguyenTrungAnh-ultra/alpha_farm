import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

"""
Portfolio Manager
==================
Manages accepted strategies with competition criteria filtering.

Note: Although the CRITERIA dictionary defines Sharpe, CAGR, Max Drawdown, 
Profit Factor, and Calmar, the actual checks in `meets_criteria` and 
`cleanup_portfolio` are restricted solely to Sharpe Ratio (> 1.3) and 
CAGR (> 15%). Other metrics are not enforced during strategy filtering.

Additionally, correlation is evaluated for warning/logging purposes only. 
Strategies exceeding the correlation threshold are NOT rejected or pruned from 
the portfolio (correlation rejection logic is currently commented out).
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


# ─── Competition Criteria ────────────────────────────────────────────
CRITERIA = {
    'sharpe_ratio':     {'min': 1.3,   'label': 'Sharpe'},
    'cagr':             {'min': 0.15,  'label': 'CAGR'},      # 15%
    'max_drawdown_pct': {'min': -35.0, 'label': 'MaxDD%'},     # ≥ -35%
    'profit_factor':    {'min': 1.2,   'label': 'PF'},
    'calmar_ratio':     {'min': 1.1,   'label': 'Calmar'},
}

MAX_CORRELATION = 0.5
MIN_TRADES = 20  # Minimum trades for statistical significance


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
    
    def meets_criteria(self, metrics: dict) -> tuple[bool, list[str]]:
        """
        Check if metrics meet active competition criteria.
        
        Note: Currently, only Sharpe Ratio (> 1.3) and CAGR (> 15%) are 
        enforced. Other metrics defined in the CRITERIA dictionary (such as 
        Max Drawdown, Profit Factor, and Calmar Ratio) are not verified.
        """
        fail_reasons = []
        
        # Check Sharpe
        sharpe = metrics.get('sharpe_ratio', 0)
        if sharpe <= 1.3:
            fail_reasons.append(f"Sharpe {sharpe:.2f} <= 1.3")
            
        # Check CAGR
        cagr = metrics.get('cagr', 0)
        if cagr <= 0.15:
            fail_reasons.append(f"CAGR {cagr*100:.1f}% <= 15%")
            
        return len(fail_reasons) == 0, fail_reasons

    def cleanup_portfolio(self) -> int:
        """
        Quét qua toàn bộ danh mục hiện tại và xóa bỏ các chiến lược 
        không đạt tiêu chuẩn (chỉ kiểm tra Sharpe > 1.3 và CAGR > 15%).
        Xóa file .py, _equity.csv, _positions.csv và cập nhật lại JSON.
        
        Note: Các tiêu chí khác trong CRITERIA như Max Drawdown, Profit Factor, 
        và Calmar Ratio không được kiểm tra ở đây.
        """
        removed_count = 0
        valid_strategies = []
        valid_equity = []
        valid_positions = []
        
        for idx, s in enumerate(self.strategies):
            m = s.get('metrics', {})
            sharpe = m.get('sharpe_ratio', 0)
            cagr = m.get('cagr', 0)
            
            if sharpe > 1.3 and cagr > 0.15:
                valid_strategies.append(s)
                valid_equity.append(self._equity_curves[idx])
                valid_positions.append(self._position_series[idx])
            else:
                # Xóa file liên quan
                name = s['name']
                tf = s['timeframe']
                
                for ext in ['.py', '_equity.csv', '_positions.csv']:
                    fpath = self.results_dir / f"{name}_{tf}{ext}"
                    if fpath.exists():
                        try:
                            fpath.unlink()
                        except Exception as e:
                            print(f"Error deleting {fpath}: {e}")
                
                removed_count += 1
                print(f"Removed failed strategy from portfolio: {name}_{tf} (Sharpe={sharpe}, CAGR={cagr})")
                
        if removed_count > 0:
            self.strategies = valid_strategies
            self._equity_curves = valid_equity
            self._position_series = valid_positions
            self._save_summary()
            print(f"Portfolio cleanup complete. Removed {removed_count} strategies.")
            
        return removed_count
    
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
        Evaluate strategy and add to portfolio if it passes.
        
        Note:
        - Only checks Sharpe (> 1.3) and CAGR (> 15%).
        - Returns a warning/logs if returns or positions correlation exceeds
          the max correlation threshold, but does NOT reject the strategy
          because the rejection logic for correlation is commented out.
        
        Returns
        -------
        (accepted, reason)
        """
        # ── Check criteria ──
        passed, fail_reasons = self.meets_criteria(metrics)
        if not passed:
            reason = f"REJECTED (criteria): {'; '.join(fail_reasons)}"
            return False, reason
        
        # ── Check correlation ──
        max_corr_returns = self.compute_max_correlation(equity_curve)
        max_corr_positions = self.compute_max_position_correlation(positions)
        
        if max_corr_returns > self.max_correlation:
            reason = f"WARNING (return correlation): max_corr_returns={max_corr_returns:.2f} > {self.max_correlation}"
            # return False, reason  # Bỏ tiêu chí corr
            print(f"  ⚠️ {reason}")
            
        if max_corr_positions > self.max_correlation:
            reason = f"WARNING (position correlation): max_corr_positions={max_corr_positions:.2f} > {self.max_correlation}"
            # return False, reason  # Bỏ tiêu chí corr
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
            json.dump(summary, f, indent=2, ensure_ascii=False)
    
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
