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
    
    if not py_files:
        print("No unpushed strategies found in agent/results/", flush=True)
        return
        
    print(f"Found {len(py_files)} unpushed strategies. Starting submission...", flush=True)
    
    for filepath in py_files:
        filename = os.path.basename(filepath)
        print(f"\n[{filename}] Submitting...", flush=True)
        
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
                print(f"[{filename}] SUCCESS! (Info/Warning: {err_msg}) File moved to pushed/.", flush=True)
            else:
                print(f"[{filename}] SUCCESS! File moved to pushed/.", flush=True)
        else:
            print(f"[{filename}] FAILED or ERRORED: {err_msg}", flush=True)
            
        print("Sleeping 15 seconds cooldown...", flush=True)
        time.sleep(15)
            
if __name__ == "__main__":
    main()
