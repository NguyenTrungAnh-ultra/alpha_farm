# AGENT_EXP
 
 ## TÓM TẮT CHAT
 - Xây tool `auto_submit.py` nộp chiến lược XNOQuant tự động qua Playwright.
 - Chạy pipeline: Sinh code -> Format -> Validate -> Nộp web.
 - Gặp lỗi simulation: Timeout, web chậm, lỗi code pandas/numpy trên server.
 - Debug web: Viết script connect Chrome CDP, chụp màn hình, check DOM.
 - Sửa chiến lược: Sửa cách tính `entry_price`, bỏ `iloc`.
 - Thành công nộp tự động. Kiểm tra kết quả, ghi nhận lỗi vào `weaknesses.md`.
 - Thực hiện reverse engineering thành công toàn bộ công thức tính toán chỉ số hiệu năng trên sàn XNOQuant, giải mã các lệch pha dữ liệu.
 
 ## KINH NGHIỆM THỰC CHIẾN (CHI TIẾT)
 
 ### 1. CODE CHIẾN LƯỢC CHO XNOQUANT
 - CHỐNG CHỈ ĐỊNH `iloc`: Hàm filter/session hay dùng `iloc` sẽ gây lỗi khi lên server do data shape khác. Dùng mask/vectorize an toàn hơn.
 - CÁCH LẤY ENTRY PRICE CHUẨN: Để tính Take Profit/Stop Loss, CẦN lưu giá vào lệnh. Cách không lỗi: `close.where(điều_kiện_vào_lệnh).ffill()`. Ổn định nhất.
 - ĐỊNH DẠNG CODE: Phải tách `get_feature()`, `get_position()`. Đảm bảo code sạch, không dùng thư viện ngoài nếu server không hỗ trợ.
 
 ### 2. CÀO/TỰ ĐỘNG WEB (PLAYWRIGHT)
 - WEB SIÊU CHẬM: Đặt timeout cao (>60s). Simulation mất nhiều thời gian.
 - CHỜ ĐÚNG LÚC: `wait_for_selector` trạng thái `visible`. Không click mù.
 - HANDLE LỖI: Try-catch từng chiến lược. Cào thông báo lỗi trên UI, log ra file. Bỏ qua chiến lược lỗi để chạy tiếp. Không sập cả batch.
 - QUY TRÌNH NỘP: Dán code -> Ấn simulate -> Đợi -> Check lỗi -> (Nếu ok) Ấn publish.
 
 ### 3. CƠ CHẾ KHỚP LỆNH VÀ CÔNG THỨC CHỈ SỐ (REVERSE ENGINEERING)
 - **Cơ chế khớp lệnh:** Khớp tại mức giá `Close` của nến phát tín hiệu. Vốn ban đầu hiển thị trên Web được trừ luôn phí mở lệnh đầu tiên.
 - **Lệch pha thời gian (Date Shift):** Các timestamp ngày trên web bị lệch +1 ngày dương lịch (ví dụ: Thứ Sáu thay vì Thứ Năm), nhưng tổng số ngày giao dịch (`Trading Days`) hoàn toàn bằng nhau.
 - **Dữ liệu thiếu (Data Gaps):** API DNSE bị thiếu một số ngày giao dịch lịch sử (ví dụ: 16/07/2020 - 20/07/2020), trong khi dữ liệu gốc của XNOQuant có đủ. Điều này dẫn tới lệch nhẹ số lệnh (>99.4% khớp) đối với các chiến lược sử dụng chỉ báo (CCI, ATR, SMA...) do giá trị chỉ báo bị lệch vài nến.
 - **Sharpe Ratio:** Tính trên chuỗi tỷ suất lợi nhuận vốn cố định (Constant Capital Returns: $\Delta\text{PnL} / 1\text{e}9$) với `ddof=0` (độ lệch chuẩn tổng thể).
 - **Volatility:** Tính trên chuỗi tỷ suất lợi nhuận lũy kế (Rolling Equity Returns: `.pct_change()`) với `ddof=1` (độ lệch chuẩn mẫu).
 - **Sortino Ratio:** Tính trên chuỗi Rolling Equity Returns với downside deviation chuẩn hóa trên tổng số kỳ $N$ (thay vì chỉ số ngày âm).
 - **VaR (95%):** Parametric VaR tính trên Rolling Equity Returns dùng `ddof=1` standard deviation.
 - **CAGR:** Số năm được quy đổi bằng số ngày giao dịch thực tế chia cho 252 ($\text{Trading Days} / 252$), không dùng ngày dương lịch.
 
 ### 4. DEBUGGING & PYTHON
 - NHÌN XUYÊN BROWSER: Dùng script gọi CDP (`inspect_browser_tabs.py`) chụp ảnh màn hình + list tab để biết tool đang kẹt ở giao diện nào, rất hữu ích khi chạy ẩn/nền.
 - TERMINAL WINDOWS: Lỗi in UTF-8 (Tiếng Việt) làm sập script. Giải pháp: `sys.stdout.reconfigure(encoding='utf-8')` đầu file.
 - KIỂM TRA TRƯỚC: Viết script `verify_formatted_code.py` test đầu ra text trước khi ném cho Playwright. Phát hiện lỗi syntax từ sớm.
 
 ### 5. BÀI HỌC QUẢN LÝ TASK
 - Tập trung fix đúng lỗi user yêu cầu, không lan man.
 - Ghi chú điểm yếu thuật toán vào file riêng ngay khi thấy fail.

