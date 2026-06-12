import os
import sys
import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from openai import OpenAI

# Force UTF-8 for Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Add project root to path
PROJECT_ROOT = str(Path(__file__).parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.build_deepseek_prompt import build_deepseek_system_prompt, build_deepseek_user_prompt
from agent.extract_json_response import extract_json

TIMEFRAME_ORDER = ["5m", "10m", "15m", "30m", "1m"]

def load_experience_log(filepath: str = "agent/experience_log.md") -> str:
    """Load the combat experience log."""
    path = Path(PROJECT_ROOT) / filepath
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_existing_ideas(results_dir: str = "agent/results/ideas") -> list[dict]:
    """Load all existing valid strategies."""
    path = Path(PROJECT_ROOT) / results_dir
    path.mkdir(parents=True, exist_ok=True)
    ideas = []
    for file in path.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "name" in data:
                    ideas.append(data)
        except Exception:
            continue
    return ideas

def get_api_key() -> str:
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        api_path = Path(PROJECT_ROOT) / "api.txt"
        if api_path.exists():
            with open(api_path, "r", encoding="utf-8") as f:
                key = f.read().strip()
    if not key:
        raise ValueError("DeepSeek API Key not found. Please set DEEPSEEK_API_KEY or create api.txt")
    return key

def run_deepseek_pipeline(
    n_strategies: int = 50,
    results_dir: str = "agent/results/ideas",
):
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           DEEPSEEK IDEA GENERATOR (CACHE OPTIMIZED)          ║
║  Target: {n_strategies} ideas | Model: deepseek-v4-pro             ║
║  Timeframes: {', '.join(TIMEFRAME_ORDER)}                      ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    out_dir = Path(PROJECT_ROOT) / results_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    experience = load_experience_log()
    existing_ideas = load_existing_ideas(results_dir)
    tried_names = {s["name"] for s in existing_ideas}
    
    # 1. INIT CLIENT
    api_key = get_api_key()
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    # 2. BUILD STATIC SYSTEM PROMPT (Ensures Cache Hit)
    system_prompt = build_deepseek_system_prompt(experience)

    start_time = time.time()
    accepted = 0
    errors = 0

    for round_num in range(1, n_strategies + 1):
        timeframe = TIMEFRAME_ORDER[(round_num - 1) % len(TIMEFRAME_ORDER)]
        
        print("─" * 60)
        print(f"  Round {round_num}/{n_strategies} | TF={timeframe} | Generated: {accepted} | Elapsed: {int((time.time()-start_time)/60)}m")
        print("─" * 60)

        # 3. BUILD DYNAMIC USER PROMPT
        user_prompt = build_deepseek_user_prompt(
            timeframe=timeframe,
            existing_strategies=existing_ideas,
            round_num=round_num,
            total_rounds=n_strategies,
            tried_names=list(tried_names)
        )

        print(f"  [{round_num}/{n_strategies}] Generating idea via DeepSeek...")
        
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-pro", # Used deepseek-v4-pro as requested by user
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                stream=False,
                reasoning_effort="high",
                extra_body={"thinking": {"type": "enabled"}},
                temperature=1.0,
                max_tokens=8192
            )
            
            raw_text = response.choices[0].message.content
            
            # Use extract_json to robustly parse the JSON output
            idea = extract_json(raw_text)
            
            if not idea or not isinstance(idea, dict) or "name" not in idea:
                print(f"  ❌ Failed to extract valid JSON.")
                print(f"  Raw output snippet: {raw_text[:200]}...")
                errors += 1
                time.sleep(2)
                continue

            name = idea["name"]
            
            if name in tried_names:
                print(f"  ❌ Duplicate name generated: {name}")
                errors += 1
                continue

            # Save the idea
            safe_name = "".join(c if c.isalnum() else "_" for c in name)
            filename = f"{safe_name}_{timeframe}.json"
            filepath = out_dir / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(idea, f, indent=4, ensure_ascii=False)

            existing_ideas.append(idea)
            tried_names.add(name)
            accepted += 1
            
            print(f"  ✅ Idea: {name} ({idea.get('family', 'unknown')})")
            desc = idea.get('description', '')
            if desc:
                print(f"     {desc[:100]}...")
            print(f"  💾 Saved to {filepath}")
            
            # Short delay to avoid rate limit spikes
            time.sleep(2)

        except Exception as e:
            errors += 1
            print(f"  ❌ DeepSeek API Error: {str(e)[:150]}")
            time.sleep(5)

    total_time = time.time() - start_time
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                 DEEPSEEK PIPELINE COMPLETE                 ║
╠══════════════════════════════════════════════════════════════╣
║  Total time:       {total_time/60:6.1f} minutes                       ║
║  Rounds attempted: {n_strategies:6d}                               ║
║  Ideas generated:  {accepted:6d}                               ║
║  Errors:           {errors:6d}                               ║
╚══════════════════════════════════════════════════════════════╝
    """)

if __name__ == "__main__":
    try:
        run_deepseek_pipeline(n_strategies=50)
    except Exception as e:
        print(f"Failed to start DeepSeek pipeline: {e}")
        traceback.print_exc()
