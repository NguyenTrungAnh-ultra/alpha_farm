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
    
    # Initialize local model client for self-correction if main model is not local
    local_chat = None
    if model != "ollama-local":
        try:
            from agent.ollama_client import OllamaChatClient
            local_chat = OllamaChatClient(model="qwen3.5:4b", verbose=False)
            print("[Pipeline] Local Ollama client initialized for self-correction.")
        except Exception as e:
            print(f"[Pipeline] Warning: Failed to init local Ollama for self-correction: {e}")
    else:
        local_chat = chat
        
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
            )
            
            # Send JSON request
            raw_text = chat.send(idea_prompt) if hasattr(chat, 'send') else ""
            
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
            
            # Now, enter the self-correction loop
            max_correction_attempts = 1
            correction_attempt = 0
            validation_passed = False
            
            from agent.convert_ideas import generate_python_code
            from xno_sdk.emulator import XNOPlatformEmulator
            from agent.prompts import build_correction_prompt
            from sandbox_prefixer import apply_prefixes
            emulator = XNOPlatformEmulator(verbose=False)
            
            while correction_attempt < max_correction_attempts:
                correction_attempt += 1
                name = idea.get('name', f'Idea_{round_num}_{tf}')
                # Clean name to be valid python identifier
                import re
                name = re.sub(r'[^a-zA-Z0-9_]', '', name)
                idea['name'] = name
                idea['timeframe'] = tf
                
                py_code = generate_python_code(idea)
                # =====================================================================
                # [THÊM MỚI] KÍCH HOẠT BỨC TƯỜNG PHÒNG NGỰ - SANDBOX PREFIXER
                # =====================================================================
                py_code, idea, was_modified, fix_log = apply_prefixes(py_code, idea)
                
                if was_modified:
                    print(f"  [Attempt {correction_attempt}/{max_correction_attempts}] 🛡️ [Prefixed] Đã can thiệp sửa mã bằng sandbox_prefixer:")
                    for log_item in fix_log:
                        print(f"  {log_item}")
                # =====================================================================

                # Define paths
                ideas_folder = os.path.join(PROJECT_ROOT, "agent", "results", "ideas")
                os.makedirs(ideas_folder, exist_ok=True)
                
                json_path = os.path.join(ideas_folder, f"{name}_{tf}.json")
                py_path = os.path.join(PROJECT_ROOT, "agent", "results", f"{name}_{tf}.py")
                
                # Write to temp file for sandbox validation
                with open(py_path, 'w', encoding='utf-8') as f:
                    f.write(py_code)
                    
                print(f"  [Attempt {correction_attempt}/{max_correction_attempts}] Validating {name} in sandbox...")
                
                try:
                    metrics = emulator.get_metrics(py_path, tf)
                    sharpe = metrics.get('sharpe_ratio', 0.0)
                    cagr = metrics.get('cagr', 0.0)
                    
                    if sharpe >= 1.3:
                        print(f"  ✅ Validation passed! Sharpe: {sharpe:.4f} | CAGR: {cagr*100:.2f}%")
                        # Write JSON
                        with open(json_path, 'w', encoding='utf-8') as f:
                            json.dump(idea, f, indent=4, ensure_ascii=False)
                        print(f"  💾 Saved JSON to {json_path}")
                        print(f"  💾 Saved Python to {py_path}")
                        validation_passed = True
                        tried_names.add(name)
                        break
                    else:
                        print(f"  ❌ Discarded: Low Sharpe Ratio ({sharpe:.4f} < 1.3)")
                        # Delete python file and break correction loop (no retry for performance)
                        if os.path.exists(py_path):
                            os.remove(py_path)
                        break
                except Exception as e:
                    error_msg = traceback.format_exc()
                    print(f"  ❌ Sandbox Error: {type(e).__name__}: {e}")
                    
                    # Clean up the python file
                    if os.path.exists(py_path):
                        try:
                            os.remove(py_path)
                        except:
                            pass
                            
                    if correction_attempt < max_correction_attempts:
                        correction_chat = local_chat if local_chat is not None else chat
                        print(f"  🔄 Retrying self-correction using local model ({getattr(correction_chat, 'model', 'default')})...")
                        # Build correction prompt
                        correction_prompt = build_correction_prompt(json.dumps(idea, indent=4), error_msg)
                        
                        # Send correction prompt to LLM
                        raw_text = correction_chat.send(correction_prompt) if hasattr(correction_chat, 'send') else ""
                        corrected_idea = extract_json(raw_text)
                        
                        if corrected_idea:
                            idea = corrected_idea
                        else:
                            print("  ❌ Failed to parse corrected JSON from LLM.")
                            break
                    else:
                        print("  ❌ Out of correction attempts. Discarding idea.")
                        
            if validation_passed:
                consecutive_errors = 0
                existing_ideas.append(idea)
                accepted += 1
            else:
                errors += 1
                
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
    if local_chat and local_chat is not chat and hasattr(local_chat, 'stop_keepalive'):
        local_chat.stop_keepalive()
    if hasattr(chat, 'stop_keepalive'):
        chat.stop_keepalive()
    return existing_ideas

if __name__ == "__main__":
    try:
        cookies = load_cookies()
        run_pipeline(cookies=cookies, n_strategies=50, model="thinking")
    except Exception as e:
        print(f"Failed to start pipeline: {e}")
