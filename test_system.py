import sys
import os
from pathlib import Path

# Thêm thư mục gốc vào đường dẫn hệ thống
PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.pipeline import run_pipeline, load_cookies
from agent.convert_ideas import main as convert_main
from optimize_all_v2 import main as optimize_main

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
        optimize_main()
    except Exception as e:
        print(f"Lỗi bước tối ưu hóa: {e}")

    print("\n" + "="*80)
    print(" KẾT THÚC TEST ".center(80))
    print("="*80)

if __name__ == "__main__":
    test_system()
