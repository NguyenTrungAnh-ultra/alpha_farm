import os
import sys
import pandas as pd

# Ensure we can import from xno_sdk and backtest
project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_dir)

from backtest.engine import XNOBacktestEngine, load_data
from backtest.metrics import compute_metrics
from agent.results.Basis_Arbitrage_QuarterOscillate import CustomStrategy

def main():
    timeframes = ['5m', '10m', '15m', '30m']
    results = []
    engine = XNOBacktestEngine()
    
    for tf in timeframes:
        print(f"\\n--- Testing Basis Arbitrage on {tf} ---")
        try:
            df = load_data(tf)
            strategy = CustomStrategy()
            res = engine.run(strategy, df)
            metrics = compute_metrics(res)
            
            results.append({
                'Timeframe': tf,
                'Total Trades': metrics['total_trades'],
                'Win Rate': metrics['win_rate_pct'],
                'Return %': metrics['cumulative_return_pct'],
                'Sharpe': metrics['sharpe_ratio'],
                'Max Drawdown %': metrics['max_drawdown_pct'],
                'PnL': metrics['unrealized_pnl']
            })
            print(f"[{tf}] Trades: {metrics['total_trades']}, Sharpe: {metrics['sharpe_ratio']:.2f}, Return: {metrics['cumulative_return_pct']:.2f}%, MDD: {metrics['max_drawdown_pct']:.2f}%")
        except Exception as e:
            print(f"Error testing {tf}: {e}")
            
    if results:
        res_df = pd.DataFrame(results)
        print("\\n=== BASIS ARBITRAGE RESULTS ===")
        print(res_df.to_string(index=False))
        
        # Save to CSV
        out_csv = os.path.join(os.path.dirname(__file__), "results", "basis_arbitrage_report.csv")
        res_df.to_csv(out_csv, index=False)
        print(f"Saved to {out_csv}")
    else:
        print("No results generated.")

if __name__ == "__main__":
    main()
