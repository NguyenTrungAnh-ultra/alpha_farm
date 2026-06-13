import os
import sys
import glob
sys.path.insert(0, 'f:/Projects/alpha_farm')
from xno_sdk.emulator import XNOPlatformEmulator

emulator = XNOPlatformEmulator(verbose=False)
files = glob.glob('f:/Projects/alpha_farm/agent/results/failed/*.py')
for f in files:
    print(f"Testing {os.path.basename(f)}:")
    try:
        emulator.get_metrics(f, '10m')
        print("  Success locally")
    except Exception as e:
        print(f"  Local Error: {e}")
