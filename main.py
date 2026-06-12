import os
import sys
import time
from pathlib import Path

# Fix Windows terminal UTF-8 encoding issue
sys.stdout.reconfigure(encoding='utf-8')

# Thêm thư mục gốc vào đường dẫn hệ thống
PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.pipeline import run_pipeline, load_cookies

def check_and_get_cookies():
    cookie_path = os.path.join(PROJECT_ROOT, "cookies.txt")
    
    while True:
        try:
            cookies = load_cookies(cookie_path)
            if cookies and len(cookies) > 20:
                return cookies
        except Exception:
            pass # Chuyển xuống in thông báo lỗi
            
        print("\n" + "="*80)
        print(" LỖI: KHÔNG TÌM THẤY COOKIE ĐĂNG NHẬP HOẶC COOKIE HẾT HẠN!".center(80))
        print("="*80)
        print("Hệ thống Google chặn việc lấy Cookie tự động bằng Bot.")
        print("Do đó, bạn cần cung cấp Cookie thủ công vào file cookies.txt:")
        print("\n[HƯỚNG DẪN LẤY COOKIE]")
        print("1. Mở trình duyệt Chrome/Edge.")
        print("2. Truy cập vào trang: https://aistudio.google.com/app/prompts/new_chat")
        print("3. Đăng nhập tài khoản Google.")
        print("4. Bấm F12 (Mở Developer Tools) -> Chọn tab 'Network'.")
        print("5. F5 lại trang, bấm vào một request bất kỳ (ví dụ 'new_chat').")
        print("6. Kéo xuống phần 'Request Headers', copy toàn bộ nội dung của biến 'cookie:'.")
        print("7. Tạo/mở file 'cookies.txt' trong thư mục dự án và dán đoạn mã đó vào.")
        print("="*80)
        
        choice = input("\nBạn đã dán cookie vào file 'cookies.txt' chưa? (y/n/thoát): ")
        if choice.lower() == 'y':
            try:
                cookies = load_cookies(cookie_path)
                if cookies:
                    return cookies
            except Exception:
                print("Vẫn chưa đọc được Cookie hợp lệ. Hãy kiểm tra lại file cookies.txt!")
        elif choice.lower() in ['thoat', 'exit', 'quit']:
            sys.exit(0)
        else:
            print("Vui lòng cập nhật file cookies.txt để tiếp tục!")
            time.sleep(2)

def main():
    print("="*80)
    print("  KHỞI ĐỘNG HỆ THỐNG XNOQUANT AUTO-FARM ".center(80))
    print("="*80)
    
    # 1. Trợ lý Cookie
    cookies = check_and_get_cookies()
    print("\n✅ Đã nạp Cookie thành công! Khởi động động cơ AI...")
    
    # 2. Khởi chạy Pipeline
    run_pipeline(
        cookies=cookies,
        n_strategies=100,             # Số lượng vòng lặp AI
        model="pro",                  # Sử dụng mô hình Gemini Pro
        n_trials=100,                 # Số vòng chạy Bayesian Optimization
        objective="total_return_pct", # Tối đa hóa lợi nhuận (bỏ qua Sharpe)
        direction="maximize",         # Mục tiêu tăng trưởng
        auto_submit=False             # Tắt Auto Submit tạm thời để chạy ngầm không bị kẹt GUI
    )

if __name__ == "__main__":
    main()
