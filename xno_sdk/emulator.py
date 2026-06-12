import importlib.util
import os
import sys
import uuid
import re
import pandas as pd
from typing import Dict, Any

from xno_sdk.engine import SimpleAlgorithm
from backtest.engine import XNOBacktestEngine, load_data, BacktestResult
from backtest import reporting

class XNOPlatformEmulator:
    """
    Giả lập 1:1 môi trường thực thi của nền tảng XNOQuant.
    Nhận raw source code file (.py), bắt lỗi Sandbox/AST,
    chạy chiến lược và tính toán metrics chính xác như web.
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.engine = XNOBacktestEngine()

    def load_strategy_from_file(self, filepath: str) -> type:
        """Load class chiến lược từ raw file .py (giống web 100%)."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Không tìm thấy file: {filepath}")
            
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_code = f.read()

        # Format code hệt như lúc chuẩn bị submit lên web (strip imports, __dict__, __init__)
        try:
            from agent.auto_submit import format_code_for_xno
            clean_code = format_code_for_xno(raw_code)
        except ImportError:
            raise RuntimeError("Không thể import format_code_for_xno từ agent.auto_submit")

        # Thêm lại đúng 1 dòng import duy nhất được phép để module nhận diện được SimpleAlgorithm
        # Điều này không vi phạm sandbox vì nó không nằm trong code của user
        module_code = "from xno_sdk.engine import SimpleAlgorithm\n\n" + clean_code

        # Tạo module name ngẫu nhiên để tránh đụng độ cache
        module_name = f"xno_strategy_{uuid.uuid4().hex[:8]}"
        
        # Load module từ string thay vì từ file
        module = type(sys)(module_name)
        module.__file__ = filepath
        sys.modules[module_name] = module

        try:
            exec(module_code, module.__dict__)
        except Exception as e:
            raise RuntimeError(f"Lỗi cú pháp hoặc runtime khi load code đã format từ {filepath}:\nCode:\n{module_code}\nLỗi: {e}")
            
        # Tìm class kế thừa từ SimpleAlgorithm
        strategy_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, SimpleAlgorithm) and attr is not SimpleAlgorithm:
                strategy_class = attr
                break
                
        if strategy_class is None:
            raise ValueError(f"Không tìm thấy class kế thừa từ SimpleAlgorithm trong {filepath}")
            
        # Lưu lại source code đã format để sandbox AST validation đọc trực tiếp
        strategy_class._emulator_source_code = clean_code
            
        return strategy_class

    def run_file(self, filepath: str, timeframe: str) -> BacktestResult:
        """
        Thực thi toàn bộ flow: load data -> load strategy -> run -> return BacktestResult.
        """
        # 1. Load data thô (fill Volume NaN bằng 0.0 như xno_sdk, nhưng không xóa nến)
        if self.verbose:
            print(f"Loading data for {timeframe}...")
            
        df = load_data(timeframe=timeframe)
        df['Volume'] = df['Volume'].fillna(0.0)
        
        # 2. Load strategy
        if self.verbose:
            print(f"Loading strategy from {filepath}...")
            
        strategy_class = self.load_strategy_from_file(filepath)
        strategy = strategy_class()  # Khởi tạo không truyền tham số (dùng mặc định trong code)
        
        # 3. Chạy qua backtest engine
        if self.verbose:
            print("Running backtest engine...")
            
        result = self.engine.run(strategy, df)
        
        if self.verbose:
            print("Backtest completed.")
            
        return result

    def get_metrics(self, filepath: str, timeframe: str) -> Dict[str, Any]:
        """Chạy và lấy dictionary metrics."""
        result = self.run_file(filepath, timeframe)
        metrics = reporting.compute_metrics(result)
        return metrics

    def print_report(self, filepath: str, timeframe: str):
        """In ra bảng report giống định dạng leaderboard."""
        result = self.run_file(filepath, timeframe)
        print(f"\n{'='*60}")
        print(f"XNOQUANT EMULATOR REPORT: {os.path.basename(filepath)}")
        print(f"{'='*60}")
        reporting.print_summary(result)
