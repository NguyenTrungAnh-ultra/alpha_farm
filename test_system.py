import sys
import os
from pathlib import Path

# Thêm thư mục gốc vào đường dẫn hệ thống
from strategy_workflows.GenerateStrategies import run_pipeline, load_cookies
from strategy_workflows.ConvertLegacyIdeas import main as convert_main
from main import cmd_optimize

def test_system():
    print("="*80)
    print(" BẮT ĐẦU TEST HỆ THỐNG (CHỈ SINH 1 CHIẾN LƯỢC) ".center(80))
    print("="*80)
    
    try:
        cookies = load_cookies()
    except Exception as e:
        print(f"Lỗi tải cookies (bỏ qua nếu dùng local): {e}")
        cookies = None

    print("\n--- BƯỚC 1: SINH Ý TƯỞNG ---")
    try:
        run_pipeline(
            cookies=cookies,
            n_strategies=1,  # Chỉ sinh 1 chiến lược để test nhanh
            model="ollama-local",     # Sử dụng Ollama local
            request_delay=2.0
        )
    except Exception as e:
        print(f"Lỗi bước sinh ý tưởng: {e}")

    print("\n--- BƯỚC 2: CHUYỂN ĐỔI SANG CODE PYTHON & KIỂM THỬ SANDBOX ---")
    try:
        convert_main()
    except Exception as e:
        print(f"Lỗi bước chuyển đổi: {e}")

    print("\n--- BƯỚC 3: TỐI ƯU HÓA BAYESIAN ---")
    try:
        class Args:
            n_trials = 5
        cmd_optimize(Args())
    except Exception as e:
        print(f"Lỗi bước tối ưu hóa: {e}")

    print("\n" + "="*80)
    print(" KẾT THÚC TEST ".center(80))
    print("="*80)

if __name__ == "__main__":
    test_system()
