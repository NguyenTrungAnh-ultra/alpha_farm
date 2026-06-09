import json

with open(r'd:\IU\Data_Science_talent_Competition_2026\test.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i, c in enumerate(nb['cells']):
    ct = c['cell_type']
    src = ''.join(c['source'])
    print(f"=== Cell {i} ({ct}) ===")
    print(src)
    print()
