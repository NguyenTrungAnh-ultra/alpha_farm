import os
import sys
import glob
import logging
import time

# Configure logging to print to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Ensure agent can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent.auto_submit import run_auto_submit

def main():
    results_dir = os.path.join(os.path.dirname(__file__), "agent", "results")
    py_files = glob.glob(os.path.join(results_dir, "*.py"))
    
    # Filter out init files or others if necessary
    py_files = [f for f in py_files if not os.path.basename(f).startswith("__")]
    
    print("\n" + "★" * 80, flush=True)
    print(f"🔄 [NEW LOOP] Scanning agent/results/ at {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    if not py_files:
        print("   No unpushed strategies found.", flush=True)
        print("★" * 80 + "\n", flush=True)
        return
        
    print(f"   Found {len(py_files)} unpushed strategies. Starting submission...", flush=True)
    print("★" * 80 + "\n", flush=True)
    
    for filepath in py_files:
        filename = os.path.basename(filepath)
        print("┌" + "─" * 78 + "┐", flush=True)
        print(f"│ 📤 SUBMITTING STRATEGY: {filename:<53} │", flush=True)
        print("└" + "─" * 78 + "┘", flush=True)
        
        # Extract timeframe from filename (e.g., ..._10m.py -> 10m)
        tf_part = filename.split('_')[-1].replace('.py', '')
        tf = tf_part if tf_part in ['1m', '3m', '5m', '10m', '15m', '30m', '60m'] else '10m'
        
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
            
        success, err_msg = run_auto_submit(
            strategy_code=code,
            timeframe=tf,
            filepath=filepath
        )
        
        if success:
            if err_msg:
                print(f"✅ SUCCESS: {filename} (Info/Warning: {err_msg})", flush=True)
            else:
                print(f"✅ SUCCESS: {filename}", flush=True)
        else:
            print(f"❌ FAILED: {filename} - {err_msg}", flush=True)
            
        print("💤 Sleeping 15 seconds cooldown...\n", flush=True)
        time.sleep(15)
            
if __name__ == "__main__":
    main()
