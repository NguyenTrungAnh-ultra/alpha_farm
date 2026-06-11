import os
import sys
import pandas as pd

project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_dir)

from backtest.engine import XNOBacktestEngine, load_data
from backtest.metrics import compute_metrics
from agent.results.HeikinAshi_EMA_Trend import CustomStrategy

def main():
    timeframes = ['15m', '30m', '60m']
    results = []
    engine = XNOBacktestEngine()
    
    for tf in timeframes:
        print(f"\\n--- Testing Heikin-Ashi on {tf} ---")
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
        print("\\n=== HEIKIN-ASHI RESULTS ===")
        print(res_df.to_string(index=False))
        
        out_csv = os.path.join(os.path.dirname(__file__), "results", "ha_trend_report.csv")
        res_df.to_csv(out_csv, index=False)
        print(f"Saved to {out_csv}")
    else:
        print("No results generated.")

if __name__ == "__main__":
    main()
