import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import os
import re
import tempfile
import time
import shutil
import warnings
from typing import Dict, Any, List

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    pass

from core_engine.PlatformEmulator import XNOPlatformEmulator
from core_engine import GenerateReport as reporting

class XNOOptimizerV2:
    """
    Optuna optimizer thế hệ 2 cho XNOQuant.
    Thay vì truyền params qua kwargs (bị cấm trên web),
    V2 sẽ sửa trực tiếp mã nguồn bằng Regex (giống hệt code sẽ submit)
    để chạy qua XNOPlatformEmulator.
    """
    def __init__(self, filepath: str, timeframe: str, param_space: Dict[str, Any], n_trials: int = 100, objective: str = 'sharpe_ratio'):
        self.filepath = filepath
        self.timeframe = timeframe
        self.param_space = param_space
        self.n_trials = n_trials
        self.objective = objective
        self.emulator = XNOPlatformEmulator(verbose=False)
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            self.original_code = f.read()

    def _inject_params(self, code: str, params: dict) -> str:
        """Thay thế các tham số mặc định trong code."""
        new_code = code
        for name, val in params.items():
            num_pattern = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
            llm_pattern = rf"self\.{name}\s*=\s*(?:int|float)\(self\.{name}\s+if\s+'{name}'\s+in\s+self\.__dict__\s+else\s+{num_pattern}\)"
            if re.search(llm_pattern, new_code):
                new_code = re.sub(llm_pattern, f"self.{name} = {repr(val)}", new_code)
                continue
                
            # Xử lý getattr
            getattr_pattern = rf"getattr\(\s*self\s*,\s*['\"]{name}['\"]\s*,\s*{num_pattern}\)"
            if re.search(getattr_pattern, new_code):
                new_code = re.sub(getattr_pattern, repr(val), new_code)
                continue
                
            # Xử lý gán cứng: self.window = 20
            hardcode_pattern = rf"self\.{name}\s*=\s*{num_pattern}"
            if re.search(hardcode_pattern, new_code):
                new_code = re.sub(hardcode_pattern, f"self.{name} = {repr(val)}", new_code)
                continue
                
        return new_code

    def run(self):
        print(f"\n{'='*60}")
        print(f"Starting optimization (V2 Emulator) for: {os.path.basename(self.filepath)}")
        print(f"Timeframe: {self.timeframe} | Trials: {self.n_trials} | Objective: {self.objective}")
        print(f"{'='*60}")
        
        # Tạo temp folder để chứa các file code sinh ra trong quá trình chạy
        temp_dir = tempfile.mkdtemp()
        
        def objective_func(trial):
            params = {}
            for name, space in self.param_space.items():
                if isinstance(space, list):
                    params[name] = trial.suggest_categorical(name, space)
                elif isinstance(space, tuple) and len(space) == 2:
                    if isinstance(space[0], int):
                        params[name] = trial.suggest_int(name, space[0], space[1])
                    else:
                        params[name] = trial.suggest_float(name, space[0], space[1])
                elif isinstance(space, tuple) and len(space) == 3:
                    if isinstance(space[0], int):
                        params[name] = trial.suggest_int(name, space[0], space[1], step=space[2])
                    else:
                        params[name] = trial.suggest_float(name, space[0], space[1], step=space[2])
                        
            # Inject params
            mutated_code = self._inject_params(self.original_code, params)
            
            # Lưu ra file tạm
            trial_file = os.path.join(temp_dir, f"trial_{trial.number}.py")
            with open(trial_file, 'w', encoding='utf-8') as f:
                f.write(mutated_code)
                
            # Chạy emulator
            try:
                metrics = self.emulator.get_metrics(trial_file, self.timeframe)
                obj_val = metrics.get(self.objective, 0.0)
                
                # Lưu thêm metrics để phân tích
                for k, v in metrics.items():
                    if isinstance(v, (int, float)):
                        trial.set_user_attr(k, float(v))
                        
                return obj_val
            except Exception as e:
                # Nếu sandbox validation fail hoặc error, return 0
                return 0.0
                
        study = optuna.create_study(direction='maximize')
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            study.optimize(objective_func, n_trials=self.n_trials, show_progress_bar=True)
            
        shutil.rmtree(temp_dir)
        
        print("\nOptimization Results:")
        print(f"Best trial: {study.best_trial.number}")
        print(f"Best {self.objective}: {study.best_value:.4f}")
        print(f"Best params: {study.best_params}")
        
        # Ghi đè file gốc
        best_code = self._inject_params(self.original_code, study.best_params)
        with open(self.filepath, 'w', encoding='utf-8') as f:
            f.write(best_code)
            
        print(f"\nOverwrote optimal parameters to file: {self.filepath}")
        return study
