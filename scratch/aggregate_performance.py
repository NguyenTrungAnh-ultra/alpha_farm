import os
import sys

# Add project root to sys.path first
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import ast
import re
import pandas as pd
from collections import defaultdict
from xno_sdk.emulator import XNOPlatformEmulator

def get_strategy_parameters(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    
    params = set()
    
    class ParamVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            if node.name == "CustomStrategy":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__algorithm__":
                        self.visit_algorithm(item)
        
        def visit_algorithm(self, func_node):
            for stmt in func_node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                            params.add(target.attr)
    
    visitor = ParamVisitor()
    visitor.visit(tree)
    return list(params)

def main():
    pushed_dir = os.path.join(PROJECT_ROOT, "agent", "results", "pushed")
    if not os.path.exists(pushed_dir):
        print(f"Directory not found: {pushed_dir}")
        return

    py_files = [f for f in os.listdir(pushed_dir) if f.endswith(".py") and f != "__init__.py"]
    
    # Filter strategies with timeframe > 5m
    valid_files = []
    for filename in py_files:
        tf_match = re.search(r'_(\d+m)\.py', filename)
        timeframe = tf_match.group(1) if tf_match else "10m"
        if timeframe not in ['1m', '3m', '5m']:
            valid_files.append((filename, timeframe))
            
    print(f"Total strategy files found: {len(py_files)}")
    print(f"Strategy files after excluding <=5m: {len(valid_files)}")
    print("Starting backtests...")
    
    emulator = XNOPlatformEmulator(verbose=False)
    
    # We will group results by param count
    grouped_results = defaultdict(list)
    errors = []
    
    for idx, (filename, timeframe) in enumerate(valid_files, 1):
        filepath = os.path.join(pushed_dir, filename)
        params = get_strategy_parameters(filepath)
        if params is None:
            print(f"[{idx}/{len(valid_files)}] Skip {filename} (cannot parse)")
            continue
            
        param_count = len(params)
        
        print(f"[{idx}/{len(valid_files)}] Backtesting {filename} ({param_count} params, {timeframe})...", flush=True)
        try:
            metrics = emulator.get_metrics(filepath, timeframe)
            grouped_results[param_count].append({
                'name': filename,
                'timeframe': timeframe,
                'param_count': param_count,
                'metrics': metrics
            })
        except Exception as e:
            print(f"  [!] Error backtesting {filename}: {e}")
            errors.append((filename, str(e)))
            
    print(f"\nBacktesting completed. Errors: {len(errors)}")
    
    # Calculate aggregate stats for each param count group
    stats = []
    for param_count, strategies in sorted(grouped_results.items()):
        total_strats = len(strategies)
        
        # Extract metrics
        sharpes = [s['metrics'].get('sharpe_ratio', 0.0) for s in strategies]
        cagrs = [s['metrics'].get('cagr', 0.0) for s in strategies]
        mdds = [s['metrics'].get('max_drawdown_pct', 0.0) for s in strategies]
        pfs = [s['metrics'].get('profit_factor', 0.0) for s in strategies]
        win_rates = [s['metrics'].get('win_rate', 0.0) for s in strategies]
        returns = [s['metrics'].get('total_return_pct', 0.0) for s in strategies]
        
        # Passes criteria: Sharpe >= 1.3, CAGR >= 15%, MDD >= -35%, PF >= 1.2, Calmar >= 1.1
        passes = 0
        for s in strategies:
            m = s['metrics']
            passed = (
                m.get('sharpe_ratio', 0.0) >= 1.3 and
                m.get('cagr', 0.0) >= 0.15 and
                m.get('max_drawdown_pct', 0.0) >= -35.0 and
                m.get('profit_factor', 0.0) >= 1.2 and
                m.get('calmar_ratio', 0.0) >= 1.1
            )
            if passed:
                passes += 1
                
        pass_rate = (passes / total_strats) * 100 if total_strats > 0 else 0
        
        # Sort strategies by Sharpe to find the best in this group
        sorted_strats = sorted(strategies, key=lambda x: x['metrics'].get('sharpe_ratio', 0.0), reverse=True)
        top_strats = sorted_strats[:3]
        
        stats.append({
            'param_count': param_count,
            'count': total_strats,
            'avg_sharpe': sum(sharpes) / total_strats,
            'avg_cagr': sum(cagrs) / total_strats,
            'avg_mdd': sum(mdds) / total_strats,
            'avg_pf': sum(pfs) / total_strats,
            'avg_win_rate': sum(win_rates) / total_strats,
            'avg_return': sum(returns) / total_strats,
            'pass_rate': pass_rate,
            'top_strategies': [f"{s['name']} (Sharpe: {s['metrics'].get('sharpe_ratio', 0.0):.2f}, CAGR: {s['metrics'].get('cagr', 0.0)*100:.1f}%)" for s in top_strats]
        })
        
    # Generate Markdown report
    md = []
    md.append("# Analysis of Performance by Strategy Parameter Count (Timeframes > 5m)\n")
    md.append("This report evaluates how the number of parameters in a strategy affects its overall backtest performance on the VN30F1M index, **excluding short-term timeframes (1m, 3m, 5m)**. The metrics are simulated using the local XNOPlatformEmulator.\n")
    
    md.append("## Overall Performance Ranking by Parameter Count Group\n")
    md.append("Ranked by average **Sharpe Ratio** (higher is better):\n")
    
    # Sort stats by avg_sharpe descending
    ranked_stats = sorted(stats, key=lambda x: x['avg_sharpe'], reverse=True)
    
    md.append("| Rank | Param Count | Strategy Count | Avg Sharpe | Avg CAGR | Avg MaxDD | Avg Profit Factor | Avg Win Rate | Avg Return | Pass Rate (Criteria) |")
    md.append("|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for rank, st in enumerate(ranked_stats, 1):
        md.append(f"| {rank} | **{st['param_count']} params** | {st['count']} | {st['avg_sharpe']:.3f} | {st['avg_cagr']*100:.2f}% | {st['avg_mdd']:.2f}% | {st['avg_pf']:.3f} | {st['avg_win_rate']:.2f}% | {st['avg_return']:.2f}% | {st['pass_rate']:.1f}% |")
        
    md.append("\n## Detailed Analysis by Parameter Group\n")
    for st in stats:
        md.append(f"### {st['param_count']} Parameters Group ({st['count']} strategies)\n")
        md.append(f"- **Avg Sharpe Ratio:** {st['avg_sharpe']:.3f}")
        md.append(f"- **Avg CAGR:** {st['avg_cagr']*100:.2f}%")
        md.append(f"- **Avg Max Drawdown:** {st['avg_mdd']:.2f}%")
        md.append(f"- **Avg Profit Factor:** {st['avg_pf']:.3f}")
        md.append(f"- **Avg Win Rate:** {st['avg_win_rate']:.2f}%")
        md.append(f"- **Avg Cumulative Return:** {st['avg_return']:.2f}%")
        md.append(f"- **Pass Rate of Competition Criteria:** {st['pass_rate']:.1f}% ({int(st['pass_rate']/100*st['count'])} out of {st['count']} strategies passed)")
        md.append("\n**Top 3 Strategies in this Group (by Sharpe):**")
        for rank, ts in enumerate(st['top_strategies'], 1):
            md.append(f"{rank}. {ts}")
        md.append("")
        
    if errors:
        md.append("## Error Logs during Backtesting\n")
        for fname, err in errors:
            md.append(f"- **{fname}**: {err}")
            
    output_path = os.path.join(PROJECT_ROOT, "scratch", "performance_by_param_count_gt_5m.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print(f"\nSummary report written to {output_path}")

if __name__ == "__main__":
    main()
