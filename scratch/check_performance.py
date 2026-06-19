from utilities.AppConfig import PROJECT_ROOT
import os
import re
import sys

# Add project root to sys.path
from core_engine.PlatformEmulator import XNOPlatformEmulator

def main():
    pushed_dir = os.path.join(PROJECT_ROOT, "results", "pushed")
    py_files = [f for f in os.listdir(pushed_dir) if f.endswith(".py") and f != "__init__.py"]
    
    if not py_files:
        print("No python files found.")
        return
        
    emulator = XNOPlatformEmulator(verbose=False)
    
    # Test on the first strategy
    test_file = py_files[0]
    filepath = os.path.join(pushed_dir, test_file)
    
    # Determine timeframe
    tf_match = re.search(r'_(\d+m)\.py', test_file)
    timeframe = tf_match.group(1) if tf_match else "10m"
    
    print(f"Testing emulator on: {test_file} with timeframe: {timeframe}")
    try:
        metrics = emulator.get_metrics(filepath, timeframe)
        print("Success! Metrics keys:")
        print(list(metrics.keys()))
        print("Sample metrics:")
        for k, v in list(metrics.items())[:10]:
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
