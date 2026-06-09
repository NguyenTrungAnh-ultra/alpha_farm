"""Debug script: dump raw Gemini response structure to find conversation IDs."""
import sys, json
sys.path.insert(0, r"d:\IU\Data_Science_talent_Competition_2026")

from agent.gemini_client import GeminiChat

# Load cookies
cookies_str = open(r"d:\IU\Data_Science_talent_Competition_2026\cookies.txt").read()
exec(cookies_str)

chat = GeminiChat(cookies=cookies, model="pro", verbose=True)

# Send and capture raw response
raw = chat._send_request("hello test")

# Save raw
with open(r"d:\IU\Data_Science_talent_Competition_2026\agent\debug_raw.txt", "w", encoding="utf-8") as f:
    f.write(raw)

# Parse and show structure
lines = raw.split("\n")
for i, line in enumerate(lines):
    line = line.strip()
    if not line or line.isdigit():
        continue
    try:
        outer = json.loads(line)
    except:
        continue
    
    if not isinstance(outer, list):
        continue
    
    for j, item in enumerate(outer):
        if not isinstance(item, list) or len(item) < 3:
            continue
        inner_str = item[2]
        if not isinstance(inner_str, str):
            continue
        try:
            inner = json.loads(inner_str)
        except:
            continue
        if not isinstance(inner, list):
            continue
        
        print(f"\n=== outer[{j}] inner: len={len(inner)} ===")
        for k in range(min(len(inner), 10)):
            val = inner[k]
            if val is None:
                print(f"  [{k}] = None")
            elif isinstance(val, str):
                print(f"  [{k}] = str({len(val)}): {val[:80]!r}")
            elif isinstance(val, list):
                # Show first few elements
                flat = str(val)[:200]
                print(f"  [{k}] = list(len={len(val)}): {flat}")
            elif isinstance(val, (int, float, bool)):
                print(f"  [{k}] = {val}")
            else:
                print(f"  [{k}] = {type(val).__name__}: {str(val)[:100]}")

print("\nDone. Raw saved to agent/debug_raw.txt")
