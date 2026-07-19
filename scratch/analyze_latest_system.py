import csv
import json
import os
from datetime import datetime

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

def check_targets(strat):
    # Sharpe >= 1.3
    # CAGR >= 15%
    # Max Drawdown >= -35%
    # Profit factor >= 1.3
    # Calmar >= 1.1
    c1 = strat['sharpe'] >= 1.3
    c2 = strat['cagr'] >= 15.0
    c3 = strat['mdd'] >= -35.0
    c4 = strat['pf'] >= 1.3
    c5 = strat['calmar'] >= 1.1
    return c1, c2, c3, c4, c5, all([c1, c2, c3, c4, c5])

def parse_date(date_str):
    # Try different formats
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            pass
    # If it starts with a ISO date string
    try:
        clean_str = date_str.split('.')[0].replace('T', ' ')
        return datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return datetime(2020, 1, 1)

def print_detailed_list(strats, label):
    print(f"\nDetailed list of {label}:")
    print(f"{'Timestamp':<20} | {'Strategy Name':<45} | {'Sharpe':<6} | {'CAGR':<8} | {'MaxDD':<8} | {'PF':<5} | {'Calmar':<6} | {'Status'}")
    print("-" * 120)
    for s in strats:
        c1, c2, c3, c4, c5, all_met = check_targets(s)
        status = "PASS" if all_met else "FAIL (" + ",".join([
            "S" if not c1 else "",
            "C" if not c2 else "",
            "D" if not c3 else "",
            "P" if not c4 else "",
            "Cal" if not c5 else ""
        ]).strip(",").replace(",,", ",") + ")"
        status = status.replace("FAIL ()", "FAIL")
        print(f"{s['timestamp_str']:<20} | {s['name']:<45} | {s['sharpe']:<6.2f} | {s['cagr']:<7.2f}% | {s['mdd']:<7.2f}% | {s['pf']:<5.2f} | {s['calmar']:<6.2f} | {status}")

def main():
    cutoff_date = datetime(2026, 6, 20, 0, 0, 0)
    print(f"Filtering strategies generated ON OR AFTER: {cutoff_date}\n")

    # 1. Parse leaderboard.csv
    lb_mcts = []
    lb_llm = []
    if os.path.exists('results/leaderboard.csv'):
        with open('results/leaderboard.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row.get('Timestamp', '')
                dt = parse_date(ts_str)
                if dt >= cutoff_date:
                    strat_name = row.get('Strategy', '')
                    is_mcts = strat_name.lower().startswith('mcts_')
                    
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
                        'timestamp': dt,
                        'timestamp_str': ts_str
                    }
                    if is_mcts:
                        lb_mcts.append(strat_data)
                    else:
                        lb_llm.append(strat_data)

    print(f"--- LEADERBOARD STRATEGIES (ON/AFTER {cutoff_date}) ---")
    print(f"Total LLM strategies: {len(lb_llm)}")
    print(f"Total MCTS strategies: {len(lb_mcts)}")
    
    if lb_mcts:
        print_detailed_list(lb_mcts, "MCTS Leaderboard Strategies")
        # Statistics
        n = len(lb_mcts)
        avg_sharpe = sum(s['sharpe'] for s in lb_mcts) / n
        avg_cagr = sum(s['cagr'] for s in lb_mcts) / n
        avg_mdd = sum(s['mdd'] for s in lb_mcts) / n
        avg_pf = sum(s['pf'] for s in lb_mcts) / n
        avg_calmar = sum(s['calmar'] for s in lb_mcts) / n
        met_all = sum(1 for s in lb_mcts if check_targets(s)[5])
        print(f"\nAverage Performance of MCTS Leaderboard (Latest System):")
        print(f"  Sharpe: {avg_sharpe:.2f} (Target >= 1.3)")
        print(f"  CAGR: {avg_cagr:.2f}% (Target >= 15%)")
        print(f"  MaxDD: {avg_mdd:.2f}% (Target >= -35%)")
        print(f"  Profit Factor: {avg_pf:.2f} (Target >= 1.3)")
        print(f"  Calmar: {avg_calmar:.2f} (Target >= 1.1)")
        print(f"  Pass Rate (All targets met): {met_all}/{n} ({met_all/n*100:.1f}%)")

    # 2. Parse portfolio_summary.json
    port_mcts = []
    port_llm = []
    if os.path.exists('results/portfolio_summary.json'):
        with open('results/portfolio_summary.json', mode='r', encoding='utf-8') as f:
            data = json.load(f)
        strategies = data.get('strategies', [])
        for s in strategies:
            acc_str = s.get('accepted_at', '')
            dt = parse_date(acc_str)
            if dt >= cutoff_date:
                name = s.get('name', '')
                is_mcts = name.lower().startswith('mcts_')
                metrics = s.get('metrics', {})
                
                sharpe = metrics.get('sharpe_ratio', 0.0)
                cagr = metrics.get('cagr', 0.0) * 100.0
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
                    'timestamp': dt,
                    'timestamp_str': acc_str
                }
                if is_mcts:
                    port_mcts.append(strat_data)
                else:
                    port_llm.append(strat_data)

    print("\n" + "="*50 + "\n")
    print(f"--- PORTFOLIO STRATEGIES (ON/AFTER {cutoff_date}) ---")
    print(f"Total LLM strategies: {len(port_llm)}")
    print(f"Total MCTS strategies: {len(port_mcts)}")
    
    if port_mcts:
        print_detailed_list(port_mcts, "MCTS Portfolio Strategies")
        n = len(port_mcts)
        avg_sharpe = sum(s['sharpe'] for s in port_mcts) / n
        avg_cagr = sum(s['cagr'] for s in port_mcts) / n
        avg_mdd = sum(s['mdd'] for s in port_mcts) / n
        avg_pf = sum(s['pf'] for s in port_mcts) / n
        avg_calmar = sum(s['calmar'] for s in port_mcts) / n
        met_all = sum(1 for s in port_mcts if check_targets(s)[5])
        print(f"\nAverage Performance of MCTS Portfolio (Latest System):")
        print(f"  Sharpe: {avg_sharpe:.2f} (Target >= 1.3)")
        print(f"  CAGR: {avg_cagr:.2f}% (Target >= 15%)")
        print(f"  MaxDD: {avg_mdd:.2f}% (Target >= -35%)")
        print(f"  Profit Factor: {avg_pf:.2f} (Target >= 1.3)")
        print(f"  Calmar: {avg_calmar:.2f} (Target >= 1.1)")
        print(f"  Pass Rate (All targets met): {met_all}/{n} ({met_all/n*100:.1f}%)")

if __name__ == '__main__':
    main()
