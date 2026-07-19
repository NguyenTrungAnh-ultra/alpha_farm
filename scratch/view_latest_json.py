import json
from datetime import datetime

def parse_date(date_str):
    try:
        clean_str = date_str.split('.')[0].replace('T', ' ')
        return datetime.strptime(clean_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return datetime(2020, 1, 1)

with open('results/portfolio_summary.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

strategies = data.get('strategies', [])
cutoff_date = datetime(2026, 6, 20, 0, 0, 0)

for s in strategies:
    dt = parse_date(s.get('accepted_at', ''))
    if dt >= cutoff_date:
        print(json.dumps(s, indent=2))
        print("="*40)
