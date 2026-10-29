"""
Machine resource readings for the dashboard: CPU (total and per core), RAM, GPU (nvidia-smi) and disk.

Every reader degrades on its own: a missing GPU or a failing nvidia-smi gives `gpu: None` plus a
message, never an exception.
"""

import shutil
import subprocess
import threading
import time
from typing import Dict, Optional

import psutil

from utilities.AppConfig import PROJECT_ROOT

GPU_QUERY = ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', '--format=csv,noheader,nounits']
GPU_TIMEOUT_S = 3

_cpu_lock = threading.Lock()
# The first psutil.cpu_percent call only primes the counters (returns 0.0); later calls measure
# the time since the previous call.
psutil.cpu_percent(percpu=True)


def read_gpu() -> Dict:
    """First GPU as {'util_percent', 'vram_used_mb', 'vram_total_mb'}; {'error': text} when unreadable."""
    try:
        done = subprocess.run(GPU_QUERY, capture_output=True, text=True, timeout=GPU_TIMEOUT_S)
        if done.returncode != 0:
            return {'error': f"nvidia-smi exit {done.returncode}"}
        first = done.stdout.strip().splitlines()[0]
        util, used, total = [float(part.strip()) for part in first.split(',')]
        return {'util_percent': util, 'vram_used_mb': used, 'vram_total_mb': total}
    except Exception as exc:
        return {'error': f"{type(exc).__name__}: {exc}"}


def read_system(disk_path: Optional[str] = None) -> Dict:
    with _cpu_lock:
        per_core = psutil.cpu_percent(percpu=True)
    memory = psutil.virtual_memory()
    usage = shutil.disk_usage(disk_path or PROJECT_ROOT)
    gpu = read_gpu()
    return {
        'timestamp': time.time(),
        'cpu_percent': sum(per_core) / len(per_core) if per_core else 0.0,
        'cpu_per_core': per_core,
        'ram': {'percent': memory.percent, 'used_mb': memory.used / 2**20, 'total_mb': memory.total / 2**20},
        'gpu': None if 'error' in gpu else gpu,
        'gpu_error': gpu.get('error'),
        'disk': {'path': str(disk_path or PROJECT_ROOT), 'free_gb': usage.free / 2**30,
                 'total_gb': usage.total / 2**30, 'percent': 100.0 * usage.used / usage.total},
    }
