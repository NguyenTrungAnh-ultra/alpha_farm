import csv
import json
import os
import re

def clean_percentage(val):
    if not val:
        return 0.0
    val = val.replace('%', '').strip()
    val = val.replace('+', '')
    try:
        return float(val)
    except ValueError:
        return 0.0

def clean_float(val):
    if not val:
        return 0.0
    val = val.strip().replace('+', '')
    try:
        return float(val)
    except ValueError:
        return 0.0

def clean_currency(val):
    if not val:
        return 0.0
    val = val.replace('₫', '').replace('.', '').replace(',', '').strip()
    val = val.replace('+', '')
    try:
        return float(val)
    except ValueError:
        return 0.0

def analyze_leaderboard(file_path):
    if not os.path.exists(file_path):
        print(f"Leaderboard file not found: {file_path}")
        return None

    mcts_strategies = []
    llm_strategies = []

    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            strat_name = row.get('Strategy', '')
            is_mcts = strat_name.lower().startswith('mcts_')
            
            # Extract metrics
            sharpe = clean_float(row.get('Sharpe Ratio', '0'))
            cagr = clean_percentage(row.get('CAGR', '0'))
            mdd = clean_percentage(row.get('Max Drawdown', '0'))
            pf = clean_float(row.get('Profit Factor (PF)', '0'))
            calmar = clean_float(row.get('Calmar Ratio', '0'))
            
            strat_data = {
                'name': strat_name,
                'sharpe': sharpe,
                'cagr': cagr,
                'mdd': mdd,
                'pf': pf,
                'calmar': calmar,
                'timestamp': row.get('Timestamp', '')
            }
            
            if is_mcts:
                mcts_strategies.append(strat_data)
            else:
                llm_strategies.append(strat_data)
                
    return mcts_strategies, llm_strategies

def analyze_portfolio(file_path):
    if not os.path.exists(file_path):
        print(f"Portfolio summary file not found: {file_path}")
        return None

    with open(file_path, mode='r', encoding='utf-8') as f:
        data = json.load(f)
        
    strategies = data.get('strategies', [])
    mcts_strats = []
    llm_strats = []
    
    for s in strategies:
        name = s.get('name', '')
        is_mcts = name.lower().startswith('mcts_')
        metrics = s.get('metrics', {})
        
        # In portfolio, cagr is represented as a decimal fraction, and mdd is represented as a percentage like -9.46
        sharpe = metrics.get('sharpe_ratio', 0.0)
        cagr = metrics.get('cagr', 0.0) * 100.0  # convert to percent
        mdd = metrics.get('max_drawdown_pct', 0.0)
        pf = metrics.get('profit_factor', 0.0)
        calmar = metrics.get('calmar_ratio', 0.0)
        
        strat_data = {
            'name': name,
            'sharpe': sharpe,
            'cagr': cagr,
            'mdd': mdd,
            'pf': pf,
            'calmar': calmar,
            'accepted_at': s.get('accepted_at', '')
        }
        
        if is_mcts:
            mcts_strats.append(strat_data)
        else:
            llm_strats.append(strat_data)
            
    return mcts_strats, llm_strats

def check_targets(strat):
    # Sharpe >= 1.3
    # CAGR >= 15%
    # Max Drawdown >= -35% (meaning mdd_pct >= -35%, e.g., -15% is valid, -40% is not)
    # Profit factor >= 1.3
    # Calmar >= 1.1
    c1 = strat['sharpe'] >= 1.3
    c2 = strat['cagr'] >= 15.0
    c3 = strat['mdd'] >= -35.0
    c4 = strat['pf'] >= 1.3
    c5 = strat['calmar'] >= 1.1
    return c1, c2, c3, c4, c5, all([c1, c2, c3, c4, c5])

def print_stats(strategies, label):
    if not strategies:
        print(f"No strategies in category: {label}")
        return

    n = len(strategies)
    print(f"\n=== {label} (Total: {n}) ===")
    
    avg_sharpe = sum(s['sharpe'] for s in strategies) / n
    avg_cagr = sum(s['cagr'] for s in strategies) / n
    avg_mdd = sum(s['mdd'] for s in strategies) / n
    avg_pf = sum(s['pf'] for s in strategies) / n
    avg_calmar = sum(s['calmar'] for s in strategies) / n
    
    print(f"Average Sharpe Ratio: {avg_sharpe:.3f}")
    print(f"Average CAGR (%): {avg_cagr:.2f}%")
    print(f"Average Max Drawdown (%): {avg_mdd:.2f}%")
    print(f"Average Profit Factor: {avg_pf:.3f}")
    print(f"Average Calmar Ratio: {avg_calmar:.3f}")
    
    met_sharpe = 0
    met_cagr = 0
    met_mdd = 0
    met_pf = 0
    met_calmar = 0
    met_all = 0
    
    for s in strategies:
        c1, c2, c3, c4, c5, all_met = check_targets(s)
        if c1: met_sharpe += 1
        if c2: met_cagr += 1
        if c3: met_mdd += 1
        if c4: met_pf += 1
        if c5: met_calmar += 1
        if all_met: met_all += 1
        
    print(f"Pass Rates against Target Metrics:")
    print(f"  Sharpe Ratio >= 1.3: {met_sharpe}/{n} ({met_sharpe/n*100:.1f}%)")
    print(f"  CAGR >= 15%: {met_cagr}/{n} ({met_cagr/n*100:.1f}%)")
    print(f"  Max Drawdown >= -35%: {met_mdd}/{n} ({met_mdd/n*100:.1f}%)")
    print(f"  Profit Factor >= 1.3: {met_pf}/{n} ({met_pf/n*100:.1f}%)")
    print(f"  Calmar Ratio >= 1.1: {met_calmar}/{n} ({met_calmar/n*100:.1f}%)")
    print(f"  All targets met: {met_all}/{n} ({met_all/n*100:.1f}%)")

def main():
    print("ANALYSIS OF LEADERBOARD STRATEGIES:")
    lb_mcts, lb_llm = analyze_leaderboard('results/leaderboard.csv')
    print_stats(lb_llm, "Leaderboard LLM Strategies (Historical runs)")
    print_stats(lb_mcts, "Leaderboard MCTS Strategies (Historical runs)")
    
    print("\n" + "="*50 + "\n")
    
    print("ANALYSIS OF PORTFOLIO STRATEGIES:")
    port_mcts, port_llm = analyze_portfolio('results/portfolio_summary.json')
    print_stats(port_llm, "Portfolio LLM Strategies (Accepted/Active)")
    print_stats(port_mcts, "Portfolio MCTS Strategies (Accepted/Active)")

if __name__ == '__main__':
    main()
