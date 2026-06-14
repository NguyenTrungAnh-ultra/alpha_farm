import os
import sys
import glob
import time
import logging
import msvcrt

PROJECT_ROOT = "f:/Projects/alpha_farm"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.pipeline import run_pipeline, load_cookies
from agent.convert_ideas import main as convert_ideas_main
from agent.auto_submit import run_auto_submit
from agent.mcts_pipeline import run_mcts_pipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MasterOrchestrator")

def interactive_select(options, title="Select Option:"):
    selected_idx = 0
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    first_draw = True
    num_lines = len(options) + 2
    
    try:
        while True:
            if not first_draw:
                sys.stdout.write(f"\033[{num_lines}A")
            else:
                first_draw = False

            sys.stdout.write(f"\r\033[K\033[1;33m{title}\033[0m\n")
            sys.stdout.write("\r\033[K\n")
            for i, opt in enumerate(options):
                if i == selected_idx:
                    sys.stdout.write(f"\r\033[K \033[1;36m➔  {opt}\033[0m\n")
                else:
                    sys.stdout.write(f"\r\033[K    {opt}\n")
            sys.stdout.flush()
            
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                ch = msvcrt.getch()
                if ch == b'H': # Up arrow
                    selected_idx = (selected_idx - 1) % len(options)
                elif ch == b'P': # Down arrow
                    selected_idx = (selected_idx + 1) % len(options)
            elif ch in (b'\r', b'\n'):
                break
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
    return selected_idx

def get_interactive_params():
    print("=" * 80)
    print("           ALPHA FARM MASTER PIPELINE INTERACTIVE CONFIGURATOR          ")
    print("=" * 80 + "\n")
    
    models = [
        "Gemini 3 Flash Thinking (Default)",
        "Gemini 3 Pro",
        "Gemini 3 Flash",
        "DeepSeek Thinking (requires token.txt)",
        "Local Ollama (Qwen 3.5 4B)",
        "Advanced Pro (requires Advanced tier)",
        "Advanced Flash (requires Advanced tier)",
        "Advanced Thinking (requires Advanced tier)"
    ]
    model_keys = [
        "thinking",
        "pro",
        "flash",
        "deepseek-thinking",
        "ollama-local",
        "advanced-pro",
        "advanced-flash",
        "advanced-thinking"
    ]
    
    model_idx = interactive_select(models, title="=== SELECT AI MODEL ===")
    selected_model = model_keys[model_idx]
    print(f"Selected Model: \033[1;32m{models[model_idx]}\033[0m\n")
    
    sys.stdout.write("\033[1;33m=== NUMBER OF AI STRATEGIES TO GENERATE ===\033[0m [5]: ")
    sys.stdout.flush()
    n_ai_str = input().strip()
    n_ai = 5
    if n_ai_str:
        try:
            n_ai = int(n_ai_str)
        except ValueError:
            print("Invalid input. Using default: 5")
    print(f"AI Strategies: \033[1;32m{n_ai}\033[0m\n")
    
    sys.stdout.write("\033[1;33m=== MCTS ITERATIONS PER DIMENSION (0 to skip MCTS) ===\033[0m [10000]: ")
    sys.stdout.flush()
    mcts_iter_str = input().strip()
    mcts_iter = 10000
    if mcts_iter_str:
        try:
            mcts_iter = int(mcts_iter_str)
        except ValueError:
            print("Invalid input. Using default: 10000")
    
    if mcts_iter == 0:
        print("MCTS Pipeline: \033[1;31mSKIPPED\033[0m\n")
    else:
        print(f"MCTS Iterations: \033[1;32m{mcts_iter}\033[0m\n")
        
    return selected_model, n_ai, mcts_iter

def push_strategies(results_dir: str, origin_filter: str):
    """
    Finds Python strategy files in results_dir and submits them.
    origin_filter: "llm" or "mcts"
    """
    py_files = glob.glob(os.path.join(results_dir, "*.py"))
    
    for py_file in py_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            is_mcts = "[MCTS_DISCOVERY_ENGINE]" in content
            
            if origin_filter == "llm" and is_mcts:
                continue
            if origin_filter == "mcts" and not is_mcts:
                continue
                
            filename = os.path.basename(py_file)
            print("\n┌" + "─" * 78 + "┐", flush=True)
            print(f"│ 📤 SUBMITTING {origin_filter.upper()} STRATEGY: {filename:<43} │", flush=True)
            print("└" + "─" * 78 + "┘", flush=True)
            
            # Extract timeframe from filename (e.g. Idea_1_10m.py -> 10m)
            base_name = filename.replace(".py", "")
            tf_match = base_name.split("_")[-1]
            timeframe = tf_match if tf_match in ["1m", "3m", "5m", "10m", "15m", "30m", "60m"] else "15m"
            
            success, msg = run_auto_submit(
                strategy_code=content,
                timeframe=timeframe,
                params=None,
                timeout_seconds=300,
                filepath=py_file
            )
            
            if success:
                print(f"✅ SUCCESS: {filename}", flush=True)
            else:
                print(f"❌ FAILED: {filename} - {msg}", flush=True)
                
            time.sleep(5)  # Delay between submissions to avoid rate limits
            
        except Exception as e:
            logger.error(f"Error processing {py_file}: {e}")


def run_master_pipeline():
    selected_model, n_ai, mcts_iter = get_interactive_params()

    print("\n" + "=" * 80, flush=True)
    print(f"🔄 [MASTER PIPELINE RUN STARTED AT {time.strftime('%Y-%m-%d %H:%M:%S')}]", flush=True)
    print("=" * 80 + "\n", flush=True)
    
    results_dir = os.path.join(PROJECT_ROOT, "agent", "results")
    
    # --- PHASE 1: LLM Engine ---
    logger.info("\n--- PHASE 1: LLM Idea Generation ---")
    try:
        cookies = load_cookies()
        run_pipeline(cookies=cookies, n_strategies=n_ai, model=selected_model)
    except Exception as e:
        logger.error(f"❌ LLM Pipeline failed: {e}")
        print("\n" + "!" * 80)
        print("🚨 CRITICAL ERROR IN PHASE 1: AI FAILED TO GENERATE STRATEGIES 🚨")
        print(f"Error details: {e}")
        print("Stopping master pipeline to prevent cascading failures.")
        print("!" * 80 + "\n")
        sys.exit(1)
        
    logger.info("\n--- PHASE 2: Convert LLM Ideas to Code & Sandbox Verify ---")
    try:
        convert_ideas_main()
    except Exception as e:
        logger.error(f"❌ Convert Ideas failed: {e}")
        print("\n" + "!" * 80)
        print("🚨 CRITICAL ERROR IN PHASE 2: FAILED TO CONVERT AI IDEAS TO CODE 🚨")
        print(f"Error details: {e}")
        print("Stopping master pipeline to prevent cascading failures.")
        print("!" * 80 + "\n")
        sys.exit(1)
        
    logger.info("\n--- PHASE 3: Push LLM Strategies ---")
    try:
        push_strategies(results_dir, origin_filter="llm")
    except Exception as e:
        logger.error(f"❌ Push LLM Strategies failed: {e}")
        print("\n" + "!" * 80)
        print("🚨 CRITICAL ERROR IN PHASE 3: FAILED TO PUSH AI STRATEGIES 🚨")
        print(f"Error details: {e}")
        print("Stopping master pipeline to prevent cascading failures.")
        print("!" * 80 + "\n")
        sys.exit(1)
    
    # --- PHASE 4: MCTS Engine ---
    if mcts_iter > 0:
        logger.info("\n--- PHASE 4: MCTS Alpha Discovery Engine ---")
        try:
            run_mcts_pipeline(iterations=mcts_iter)
        except Exception as e:
            logger.error(f"❌ MCTS Pipeline failed: {e}")
            print("\n" + "!" * 80)
            print("🚨 CRITICAL ERROR IN PHASE 4: MCTS DISCOVERY ENGINE FAILED 🚨")
            print(f"Error details: {e}")
            print("Stopping master pipeline to prevent cascading failures.")
            print("!" * 80 + "\n")
            sys.exit(1)
    else:
        logger.info("\n--- PHASE 4: MCTS Alpha Discovery Engine (SKIPPED) ---")
        
    # --- PHASE 5: Push MCTS Strategies ---
    if mcts_iter > 0:
        logger.info("\n--- PHASE 5: Push MCTS Strategies ---")
        try:
            push_strategies(results_dir, origin_filter="mcts")
        except Exception as e:
            logger.error(f"❌ Push MCTS Strategies failed: {e}")
            print("\n" + "!" * 80)
            print("🚨 CRITICAL ERROR IN PHASE 5: FAILED TO PUSH MCTS STRATEGIES 🚨")
            print(f"Error details: {e}")
            print("Stopping master pipeline to prevent cascading failures.")
            print("!" * 80 + "\n")
            sys.exit(1)
    else:
        logger.info("\n--- PHASE 5: Push MCTS Strategies (SKIPPED) ---")
    
    logger.info("\n==================================================")
    logger.info("         MASTER PIPELINE COMPLETED                ")
    logger.info("==================================================")

if __name__ == "__main__":
    run_master_pipeline()
