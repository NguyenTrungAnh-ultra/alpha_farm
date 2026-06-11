import os
import sys
import re
import pandas as pd
import logging
from tqdm import tqdm

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.engine import XNOBacktestEngine, load_data
from xno_sdk.engine import SimpleAlgorithm
from backtest.metrics import compute_metrics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("alpha_tester")

# Mapping rules
def translate_alpha(formula: str) -> str:
    # Basic replacements
    f = formula.replace('vwap', 'vwap_proxy')
    f = f.replace('returns', 'ret')
    f = f.replace('volume', 'vol')
    f = f.replace('open', 'self.data.pv_open')
    f = f.replace('close', 'self.data.pv_close')
    f = f.replace('high', 'self.data.pv_high')
    f = f.replace('low', 'self.data.pv_low')
    
    # advX -> self.feat.rolling_mean(vol, X)
    f = re.sub(r'adv(\d+)', r'self.feat.rolling_mean(vol, \1)', f)
    
    # We will use python eval for parsing if needed, but it's not python syntax (like ? :).
    # Let's write a simple recursive ternary parser: (cond) ? (true_val) : (false_val)
    # Actually, it's easier to just skip the ? : alphas if they are too complex, or we can write a small function to convert ? : to self.op.where
    
    # To properly translate, let's just do text replacements for known function names.
    # Note: This is a very naive replacement and might not handle all nested parentheses perfectly if not careful.
    
    # We can replace function calls using regex. Since they might be nested, we just replace the names.
    replacements = {
        r'\brank\(': 'self.feat.rolling_rank(',
        r'\bTs_Rank\(': 'self.feat.rolling_rank(',
        r'\bts_rank\(': 'self.feat.rolling_rank(',
        r'\bdelay\(': 'self.op.shift(',
        r'\bdelta\(': 'self.op.diff(',
        r'\bcorrelation\(': 'self.feat.rolling_correlation(',
        r'\bcovariance\(': 'self.feat.rolling_covariance(',
        r'\bstddev\(': 'self.feat.rolling_std(',
        r'\bts_max\(': 'self.feat.rolling_max(',
        r'\bts_min\(': 'self.feat.rolling_min(',
        r'\bTs_ArgMax\(': 'self.feat.rolling_argmax(',
        r'\bts_argmax\(': 'self.feat.rolling_argmax(',
        r'\bts_argmin\(': 'self.feat.rolling_argmin(',
        r'\bsum\(': 'self.feat.rolling_sum(',
        r'\bdecay_linear\(': 'self.feat.rolling_mean(', # User decision
        r'\bsign\(': 'self.op.sign(',
        r'\bSign\(': 'self.op.sign(',
        r'\babs\(': 'self.op.abs(',
        r'\bscale\(': '(', # Strip scale, just leave parentheses
        r'\bproduct\(': 'self.feat.rolling_prod(',
        r'\blog\(': 'np.log(',
        r'\bLog\(': 'np.log(',
    }
    
    for pat, rep in replacements.items():
        f = re.sub(pat, rep, f)
        
    f = f.replace('||', '|')
    f = f.replace('&&', '&')
    
    # Replace SignedPower(A, B) -> (self.op.sign(A) * (self.op.abs(A) ** B))
    # It's hard with regex due to nested commas. We will just use a helper regex for simple cases.
    f = re.sub(r'SignedPower\(([^,]+),\s*([^)]+)\)', r'(self.op.sign(\1) * (self.op.abs(\1) ** \2))', f)

    return f

def extract_alphas(filepath):
    alphas = {}
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find all Alpha#X: ...
    matches = re.findall(r'Alpha#(\d+):\s*(.*)', content)
    for num, formula in matches:
        # Filter out IndNeutralize, IndClass
        if 'IndNeutralize' in formula or 'IndClass' in formula:
            logger.info(f"Skipping Alpha {num} due to IndNeutralize/IndClass")
            continue
        
        # We will also skip alphas with ternary operator ? : because parsing it to self.op.where using pure regex is error-prone.
        if '?' in formula:
            logger.info(f"Skipping Alpha {num} due to ternary operator (? :) which requires complex parsing.")
            continue
            
        alphas[num] = formula
    
    return alphas

def build_strategy_class(alpha_num, formula_expr):
    # Prepare the class definition
    code = f"""
from xno_sdk.engine import SimpleAlgorithm
import numpy as np

class Alpha{alpha_num}Strategy(SimpleAlgorithm):
    def __algorithm__(self):
        vol = self.data.pv_volume
        ret = self.feat.returns(self.data.pv_close, 1)
        vwap_proxy = self.feat.sma(self.data.pv_close, 20)
        
        # Calculate alpha
        try:
            alpha = {formula_expr}
            
            # Since some alphas might be just constant or single value, ensure it's a series
            # Long when alpha > threshold, Short when alpha < -threshold
            # We use a simple Z-score to normalize the alpha across different assets/timeframes
            alpha_z = self.feat.rolling_zscore(alpha, window=60)
            
            long_zone = alpha_z > 1.0
            short_zone = alpha_z < -1.0
            flat_zone = ~long_zone & ~short_zone
            
            self.set_positions(flat_zone, position=0.0)
            self.set_positions(long_zone, position=1.0)
            self.set_positions(short_zone, position=-1.0)
        except Exception as e:
            # If evaluation fails, just stay flat
            self.set_positions(self.data.pv_close > 0, position=0.0)
"""
    return code

def main():
    alphas_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'alphas_101.md')
    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
    os.makedirs(results_dir, exist_ok=True)
    
    alphas = extract_alphas(alphas_file)
    logger.info(f"Extracted {len(alphas)} valid alphas for testing.")
    
    timeframes = ['1m', '3m', '5m', '10m', '15m', '30m', '60m']
    
    # Pre-load data to save time
    data_dict = {}
    for tf in timeframes:
        try:
            data_dict[tf] = load_data(tf)
        except Exception as e:
            logger.warning(f"Could not load data for {tf}: {e}")
            
    results = []
    
    engine = XNOBacktestEngine()
    
    for num, raw_formula in tqdm(alphas.items(), desc="Testing Alphas"):
        translated = translate_alpha(raw_formula)
        code = build_strategy_class(num, translated)
        
        # Try to compile and run
        namespace = {}
        try:
            exec(code, namespace)
            StrategyClass = namespace[f'Alpha{num}Strategy']
        except Exception as e:
            logger.error(f"Alpha {num} syntax/compilation error: {e}")
            continue
            
        for tf, df in data_dict.items():
            try:
                strategy = StrategyClass()
                res = engine.run(strategy, df)
                metrics = compute_metrics(res)
                
                results.append({
                    'Alpha': num,
                    'Timeframe': tf,
                    'Total Trades': metrics['total_trades'],
                    'Win Rate': metrics['win_rate_pct'],
                    'Return %': metrics['cumulative_return_pct'],
                    'Sharpe': metrics['sharpe_ratio'],
                    'Max Drawdown %': metrics['max_drawdown_pct'],
                    'PnL': metrics['unrealized_pnl']
                })
            except Exception as e:
                logger.error(f"Alpha {num} on {tf} execution error: {e}")
                
    # Save results
    if results:
        res_df = pd.DataFrame(results)
        res_csv_path = os.path.join(results_dir, 'report_101_alphas.csv')
        res_df.to_csv(res_csv_path, index=False)
        logger.info(f"Saved detailed results to {res_csv_path}")
        
        # Generate summary MD
        summary_path = os.path.join(results_dir, 'report_summary.md')
        with open(summary_path, 'w') as f:
            f.write("# 101 Alphas Test Summary\n\n")
            f.write("## Top 10 by Sharpe Ratio\n")
            top_sharpe = res_df.sort_values('Sharpe', ascending=False).head(10)
            f.write(top_sharpe.to_markdown(index=False))
            f.write("\n\n## Top 10 by Cumulative Return\n")
            top_ret = res_df.sort_values('Return %', ascending=False).head(10)
            f.write(top_ret.to_markdown(index=False))
        logger.info(f"Saved summary to {summary_path}")
    else:
        logger.warning("No valid results were generated.")

if __name__ == "__main__":
    main()
