import sys
import os
from pathlib import Path

# Thêm thư mục gốc vào đường dẫn hệ thống
PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.pipeline import run_pipeline, load_cookies
from agent.optimize_ideas import run_optimization

def test_system():
    print("="*80)
    print(" BẮT ĐẦU TEST HỆ THỐNG (CHỈ SINH 1 CHIẾN LƯỢC) ".center(80))
    print("="*80)
    
    try:
        cookies = load_cookies()
    except Exception as e:
        print(f"Lỗi tải cookies: {e}")
        return

    print("\n--- BƯỚC 1: SINH Ý TƯỞNG ---")
    try:
        run_pipeline(
            cookies=cookies,
            n_strategies=1,  # Chỉ sinh 1 chiến lược để test nhanh
            model="pro",     # Sử dụng Gemini Pro
            request_delay=2.0
        )
    except Exception as e:
        print(f"Lỗi bước sinh ý tưởng: {e}")

    print("\n--- BƯỚC 2: LẮP RÁP TEMPLATE & TỐI ƯU HÓA OPTUNA ---")
    try:
        run_optimization()
    except Exception as e:
        print(f"Lỗi bước tối ưu hóa: {e}")

    print("\n" + "="*80)
    print(" KẾT THÚC TEST ".center(80))
    print("="*80)

if __name__ == "__main__":
    test_system()
