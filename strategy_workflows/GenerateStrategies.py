import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utilities.AppConfig import PROJECT_ROOT
"""
Strategy Idea Generation Pipeline (XNO Engine)
=============================================
Generates Quant logic/formulas via LLM based on Experience Log.
Output: JSON files in agent/results/ideas/

Usage:
    from strategy_workflows.GenerateStrategies import run_pipeline, load_cookies
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
from llm_clients.GeminiClient import GeminiChat
from utilities.Prompts import build_idea_prompt
from pydantic import BaseModel, Field

class StrategyBlueprint(BaseModel):
    name: str
    timeframe: str
    family: str
    description: str
    macro_blueprint: str



def load_cookies(filepath: str = None) -> str:
    """
    Read the Gemini cookie string from cookies.txt (the first non-comment line).
    
    Parameters
    ----------
    filepath : str, optional
        Path to cookies file. Defaults to `cookies.txt` in the project root.
        
    Returns
    -------
    str
        The cookie string.
        
    Raises
    ------
    ValueError
        If no cookies are found in the specified file.
    """
    if filepath is None:
        filepath = os.path.join(PROJECT_ROOT, "cookies.txt")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                return line
    raise ValueError(f"No cookies found in {filepath}")

def load_deepseek_token(filepath: str = None) -> str:
    """
    Read the Deepseek authentication token from token.txt (the first non-comment line).
    
    Parameters
    ----------
    filepath : str, optional
        Path to token file. Defaults to `token.txt` in the project root.
        
    Returns
    -------
    str
        The authentication token.
        
    Raises
    ------
    ValueError
        If no token is found in the specified file.
    """
    if filepath is None:
        filepath = os.path.join(PROJECT_ROOT, "token.txt")
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                return line
    raise ValueError(f"No token found in {filepath}")

def load_experience_log(filepath: str = None) -> str:
    """
    Load the quantitative experience log from experience_log.md.
    
    This log contains insights from prior strategy failures and successes 
    and is injected into the LLM prompt to guide generation.
    
    Parameters
    ----------
    filepath : str, optional
        Path to the experience log. Defaults to `utilities/experience_log.md`.
        
    Returns
    -------
    str
        The raw markdown content of the experience log, or an empty string if 
        the file does not exist.
    """
    if filepath is None:
        filepath = os.path.join(PROJECT_ROOT, "utilities", "experience_log.md")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def load_existing_ideas(ideas_dir: str) -> list[dict]:
    """
    Load all previously generated idea blueprints from the specified ideas directory.
    
    Scans the directory for JSON files and attempts to parse their contents 
    into a list of dictionaries.
    
    Parameters
    ----------
    ideas_dir : str
        The path to the directory containing idea JSON files.
        
    Returns
    -------
    list[dict]
        A list of parsed strategy blueprints (as dictionaries).
    """
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
TIMEFRAME_ORDER = ["1m", "3m", "5m", "10m", "15m", "30m", "60m"]


# ─── Main Pipeline ──────────────────────────────────────────────────

def run_pipeline(
    cookies,
    n_strategies: int = 50,
    model: str = "thinking",
    request_delay: float = 5.0,
    results_dir: str = "results/ideas",
):
    """
    Execute the main strategy generation pipeline.
    
    Queries the LLM (Gemini, Deepseek, or Ollama depending on configuration) for
    new trading strategy blueprints. Each generated blueprint is validated against
    the StrategyBlueprint Pydantic model and verified for semantic correctness via the
    SemanticCompiler. If validation fails, it attempts self-correction using a local
    or primary LLM chat client. Validated JSON files are saved to `results/ideas/`
    for the MCTS step.
    
    Parameters
    ----------
    cookies : str
        Gemini cookie string (if using Gemini model).
    n_strategies : int, default 50
        Number of ideas/strategies to attempt to generate.
    model : str, default "thinking"
        The model identifier to use (e.g. "thinking", "deepseek-thinking", 
        "ollama-local", "ollama-9b").
    request_delay : float, default 5.0
        Delay in seconds between LLM requests (primarily for cloud APIs).
    results_dir : str, default "results/ideas"
        Directory where generated JSON blueprints will be saved.
        
    Returns
    -------
    list[dict]
        The list of all accumulated and validated strategy blueprints.
    """
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
            from llm_clients.DeepseekClient import DeepseekChatClient
            token = load_deepseek_token()
            chat = DeepseekChatClient(auth_token=token, thinking_enabled=True, verbose=True)
            print(f"[Pipeline] DeepseekChatClient ready")
        except Exception as e:
            print(f"[Pipeline] Failed to init Deepseek: {e}")
            sys.exit(1)
    elif model in ["ollama-local", "ollama-9b"]:
        model_name = "qwen3.5:9b" if model == "ollama-9b" else "qwen3.5:4b"
        try:
            from llm_clients.OllamaClient import OllamaChatClient
            chat = OllamaChatClient(model=model_name, verbose=True)
            print(f"[Pipeline] OllamaChatClient ready ({model_name})")
        except Exception as e:
            print(f"[Pipeline] Failed to init Ollama ({model_name}): {e}")
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
    if model not in ["ollama-local", "ollama-9b"]:
        try:
            from llm_clients.OllamaClient import OllamaChatClient
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
                fsa_forbidden_patterns=[],
            )
            
            # Phân luồng Local / Cloud
            schema_arg = {}
            if model == "ollama-local":
                schema_arg = {"schema": "json"}
                
            try:
                raw_text = chat.send(idea_prompt, **schema_arg) if hasattr(chat, 'send') else ""
            except Exception as e:
                print(f"  ❌ Error during chat.send: {e}")
                raw_text = ""
            
            from llm_clients.GeminiClient import extract_json
            idea_json = extract_json(raw_text)
            
            if idea_json is None:
                consecutive_errors += 1
                print(f"  ❌ Failed to extract JSON (consecutive errors: {consecutive_errors})")
                print(f"  [Debug] raw_text from model:\n{raw_text[:1000]}")
                if consecutive_errors >= 3:
                    print(f"\n  🛑 RATE LIMIT DETECTED / MODEL FAILURE — Stopping pipeline.")
                    break
                errors += 1
                continue
            
            # Pydantic Validation & Self-Correction Loop
            max_correction_attempts = 1
            correction_attempt = 0
            validation_passed = False
            
            while correction_attempt < max_correction_attempts + 1:
                try:
                    # Validate JSON against schema
                    valid_idea = StrategyBlueprint.model_validate(idea_json).model_dump()
                    
                    # Validate AST Syntax and Semantic constraints
                    from strategy_workflows.SemanticCompiler import SemanticCompiler
                    compiler = SemanticCompiler()
                    try:
                        compiler.compile_blueprint(valid_idea['macro_blueprint'])
                    except Exception as compile_e:
                        raise ValueError(f"Macro-Blueprint Semantic Error: {str(compile_e)}")
                        
                    name = valid_idea.get('name', f'Idea_{round_num}_{tf}')
                    import re
                    name = re.sub(r'[^a-zA-Z0-9_]', '', name)
                    valid_idea['name'] = name
                    valid_idea['timeframe'] = tf
                    
                    # Define paths
                    ideas_folder = os.path.join(PROJECT_ROOT, "results", "ideas")
                    os.makedirs(ideas_folder, exist_ok=True)
                    json_path = os.path.join(ideas_folder, f"{name}_{tf}.json")
                    
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(valid_idea, f, indent=4, ensure_ascii=False)
                        
                    print(f"  ✅ Validation passed! Saved JSON to {json_path}")
                    validation_passed = True
                    tried_names.add(name)
                    idea_json = valid_idea
                    break
                    
                except Exception as e:
                    import pydantic
                    error_msg = str(e)
                    print(f"  ❌ Validation Error: {error_msg}")
                    
                    failed_parts = {}
                    if isinstance(e, pydantic.ValidationError):
                        for error in e.errors():
                            field = error.get("loc")[0]
                            if field in idea_json:
                                failed_parts[field] = idea_json[field]
                    elif "Macro-Blueprint Semantic Error" in error_msg:
                        if "macro_blueprint" in idea_json:
                            failed_parts["macro_blueprint"] = idea_json["macro_blueprint"]
                            
                    if not failed_parts:
                        failed_parts = idea_json
                    
                    if correction_attempt < max_correction_attempts:
                        correction_attempt += 1
                        correction_chat = local_chat if local_chat is not None else chat
                        print(f"  🔄 Retrying self-correction using model ({getattr(correction_chat, 'model', 'default')})...")
                        
                        from utilities.Prompts import build_correction_prompt
                        correction_prompt = build_correction_prompt(json.dumps(failed_parts, indent=4), error_msg)
                        
                        schema_arg_retry = {}
                        
                        raw_text = correction_chat.send(correction_prompt, **schema_arg_retry) if hasattr(correction_chat, 'send') else ""
                        corrected_idea = extract_json(raw_text)
                        
                        if corrected_idea:
                            idea_json.update(corrected_idea)
                        else:
                            print("  ❌ Failed to parse corrected JSON from LLM.")
                            break
                    else:
                        print("  ❌ Out of correction attempts. Discarding idea.")
                        break
                        
            if validation_passed:
                consecutive_errors = 0
                existing_ideas.append(idea_json)
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
    import argparse
    parser = argparse.ArgumentParser(description="Generate trading strategies.")
    parser.add_argument("--model", type=str, default="thinking", help="Model to use: thinking, deepseek, ollama-local, ollama-9b")
    parser.add_argument("--n", type=int, default=50, help="Number of strategies to generate")
    args = parser.parse_args()

    try:
        cookies = load_cookies()
        run_pipeline(cookies=cookies, n_strategies=args.n, model=args.model)
    except Exception as e:
        print(f"Failed to start pipeline: {e}")
