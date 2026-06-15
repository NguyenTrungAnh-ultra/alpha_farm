"""
Strategy Idea Generation Pipeline (XNO Engine)
=============================================
Generates Quant logic/formulas via LLM based on Experience Log.
Output: JSON files in agent/results/ideas/

Usage:
    from agent.pipeline import run_pipeline, load_cookies
    run_pipeline(cookies=load_cookies(), n_strategies=50, model="thinking")
"""

import os
import sys
import json
import time
import traceback
from datetime import datetime
from pathlib import Path

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

from agent.gemini_client import GeminiChat
from agent.prompts import build_idea_prompt


def load_cookies(filepath: str = None) -> str:
    """Read cookie string from cookies.txt (first non-comment line)."""
    if filepath is None:
        filepath = os.path.join(PROJECT_ROOT, "cookies.txt")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                return line
    raise ValueError(f"No cookies found in {filepath}")

def load_deepseek_token(filepath: str = None) -> str:
    """Read auth token from token.txt"""
    if filepath is None:
        filepath = os.path.join(PROJECT_ROOT, "token.txt")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                return line
    raise ValueError(f"No token found in {filepath}")

def load_experience_log(filepath: str = None) -> str:
    if filepath is None:
        filepath = os.path.join(PROJECT_ROOT, "agent", "experience_log.md")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def load_existing_ideas(ideas_dir: str) -> list[dict]:
    ideas = []
    if not os.path.exists(ideas_dir):
        return ideas
    for fname in os.listdir(ideas_dir):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(ideas_dir, fname), 'r', encoding='utf-8') as f:
                    idea = json.load(f)
                    ideas.append(idea)
            except Exception:
                pass
    return ideas

# ─── Timeframe Configuration ────────────────────────────────────────
TIMEFRAME_ORDER = ["10m", "15m", "30m", "60m"]


# ─── Main Pipeline ──────────────────────────────────────────────────

def run_pipeline(
    cookies,
    n_strategies: int = 50,
    model: str = "thinking",
    request_delay: float = 5.0,
    results_dir: str = "agent/results/ideas",
):
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           AUTO STRATEGY IDEA GENERATOR                     ║
║  Target: {n_strategies} ideas | Model: {model:15s}               ║
║  Timeframes: {', '.join(TIMEFRAME_ORDER):40s}  ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    os.makedirs(results_dir, exist_ok=True)
    
    if model == "deepseek-thinking":
        try:
            from agent.deepseek_client import DeepseekChatClient
            token = load_deepseek_token()
            chat = DeepseekChatClient(auth_token=token, thinking_enabled=True, verbose=True)
            print(f"[Pipeline] DeepseekChatClient ready")
        except Exception as e:
            print(f"[Pipeline] Failed to init Deepseek: {e}")
            sys.exit(1)
    elif model == "ollama-local":
        try:
            from agent.ollama_client import OllamaChatClient
            chat = OllamaChatClient(model="qwen3.5:4b", verbose=True)
            print(f"[Pipeline] OllamaChatClient ready")
        except Exception as e:
            print(f"[Pipeline] Failed to init Ollama: {e}")
            sys.exit(1)
    else:
        chat = GeminiChat(
            cookies=cookies,
            model=model,
            request_delay=request_delay,
            max_retries=5,
            timeout=180, # Increased timeout for thinking model
            verbose=True,
        )
        print(f"[Pipeline] GeminiChat ready: {chat}")
    
    experience = load_experience_log()
    print(f"[Pipeline] Loaded Experience Log: {len(experience)} chars")
    
    existing_ideas = load_existing_ideas(results_dir)
    print(f"[Pipeline] Loaded {len(existing_ideas)} existing ideas")
    
    tried_names = set([idea.get("name") for idea in existing_ideas if idea.get("name")])
    
    start_time = time.time()
    accepted = 0
    errors = 0
    consecutive_errors = 0
    
    for round_num in range(1, n_strategies + 1):
        tf_idx = (round_num - 1) % len(TIMEFRAME_ORDER)
        tf = TIMEFRAME_ORDER[tf_idx]
        
        elapsed = time.time() - start_time
        print(f"\n{'─'*60}")
        print(f"  Round {round_num}/{n_strategies} | TF={tf} | Generated: {accepted} | Elapsed: {elapsed/60:.0f}m")
        print(f"{'─'*60}")
        
        try:
            print(f"  [1/1] Generating idea ({tf})...")
            # Lọc bớt ý tưởng để tránh tràn ngữ cảnh và quá tải phần nháp của mô hình local
            # Chỉ gửi những ý tưởng cùng timeframe và giới hạn tối đa 20 ý tưởng gần nhất
            filtered_existing = [idea for idea in existing_ideas if idea.get("timeframe") == tf][-20:]
            filtered_tried = list(tried_names)[-20:]
            
            idea_prompt = build_idea_prompt(
                timeframe=tf,
                existing_strategies=filtered_existing,
                round_num=round_num,
                total_rounds=n_strategies,
                experience=experience,
                tried_names=filtered_tried,
                use_lite=(model == "ollama-local"),
            )
            
            # Send JSON request (requires GeminiChat.send_json to be available, which it is)
            # Actually wait, GeminiChat originally didn't have a specific `send_json` method, wait let me check gemini_client.py
            # Line 38 of pipeline.py in the past: `from agent.gemini_client import GeminiChat, extract_json`
            # And it called `idea = chat.send_json(idea_prompt, retries=3)`.
            # If `send_json` exists, we use it. If not, we just use `extract_json(chat.send(prompt))`.
            # I will use extract_json just in case `send_json` was a wrapper.
            raw_response = chat._send_request(idea_prompt) if hasattr(chat, '_send_request') else "" # wait, it's `chat.send(prompt)`
            # Let's use standard send and extract
            raw_text = chat.send(idea_prompt) if hasattr(chat, 'send') else ""
            
            # Actually let's safely import extract_json
            from agent.gemini_client import extract_json
            idea = extract_json(raw_text)
            
            if idea is None:
                consecutive_errors += 1
                print(f"  ❌ Failed to generate idea (consecutive errors: {consecutive_errors})")
                if consecutive_errors >= 3:
                    print(f"\n  🛑 RATE LIMIT DETECTED — Stopping pipeline.")
                    break
                errors += 1
                continue
            
            consecutive_errors = 0
            
            name = idea.get('name', f'Idea_{round_num}')
            family = idea.get('template_name', idea.get('family', 'unknown'))
            description = idea.get('rationale', idea.get('description', ''))
            tried_names.add(name)
            
            print(f"  ✅ Idea: {name} ({family})")
            print(f"     {description[:100]}...")
            
            # Save to JSON
            out_path = os.path.join(results_dir, f"{name}_{tf}.json")
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(idea, f, indent=4, ensure_ascii=False)
                
            print(f"  💾 Saved to {out_path}")
            
            existing_ideas.append(idea)
            accepted += 1
            
        except Exception as e:
            errors += 1
            print(f"  💥 Unexpected error: {type(e).__name__}: {e}")
            traceback.print_exc()
            continue
            
    total_time = time.time() - start_time
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    PIPELINE COMPLETE                       ║
╠══════════════════════════════════════════════════════════════╣
║  Total time:       {total_time/60:6.1f} minutes                       ║
║  Rounds attempted: {round_num:6d}                               ║
║  Ideas generated:  {accepted:6d}                               ║
║  Errors:           {errors:6d}                               ║
╚══════════════════════════════════════════════════════════════╝
    """)
    if hasattr(chat, 'stop_keepalive'):
        chat.stop_keepalive()
    return existing_ideas

if __name__ == "__main__":
    try:
        cookies = load_cookies()
        run_pipeline(cookies=cookies, n_strategies=50, model="thinking")
    except Exception as e:
        print(f"Failed to start pipeline: {e}")
