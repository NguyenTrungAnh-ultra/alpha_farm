# XNOQuant Auto-Gen Architecture

account: toinguyen15102004@gmail.com
password: anhtrung15102004

## 1. Cấu trúc Thư mục

- `agent/`: Chứa các kịch bản AI tạo chiến lược (gọi LLM API), quản lý danh mục và tự động nộp bài.
- `backtest/`: Động cơ (Engine) giả lập giao dịch nội bộ, cung cấp khả năng tính toán các chỉ số (PnL, Fee, Sharpe...) và hỗ trợ tối ưu hóa tham số.
- `xno_sdk/`: Thư viện giả lập môi trường Sandbox và các toán tử/chỉ báo của XNOQuant để hỗ trợ kiểm thử cục bộ.
- `strategies/`: Thư mục lưu trữ các chiến lược sinh ra.
- `XNOQuant/`: Bản lưu các chiến lược cũ.

## 2. Hệ Thống Luật Chơi & Giới Hạn Của Sàn (XNOQuant Rules)

Dưới đây là các giới hạn và quy định chung để chiến lược có thể chạy được trên nền tảng `alpha.xnoquant.io`:

- **Khung thời gian (Universe):** Chỉ áp dụng cho hợp đồng tương lai VN30 (VN30F1M) ở các khung 1m, 3m, 5m, 10m, 15m, 30m, 60m.
- **Biến trạng thái vị thế:** Mục tiêu vị thế nằm trong dải `[-1, 1]`. Trong đó `1` = Full Long, `-1` = Full Short, `0` = Flat.
- **Nguồn dữ liệu hợp lệ:** Chỉ được phép gọi `self.data.pv_close`, `self.data.pv_volume`, và `self.data.pv_vn30_close`.
- **Luật Cấu trúc (AST Rules):**
  - Lớp chiến lược phải kế thừa `class CustomStrategy(SimpleAlgorithm)`.
  - Hàm thuật toán bắt buộc là `def __algorithm__(self):`. Không sử dụng hàm `__init__`.
  - Cấm sử dụng vòng lặp duyệt từng dòng (row-by-row). Code bắt buộc phải ở dạng Vectorized.
  - Cấm sử dụng từ khóa `import` (numpy, pandas, talib). Mọi phép toán phải thông qua `self.feat` và `self.op`.
- **Quy trình tính điểm (Leaderboard):**
  - Điểm tổng của thí sinh dựa trên tính lũy kế (Cumulative). Nhiều chiến lược tốt sẽ tăng điểm tổng.
  - Sàn áp dụng hình phạt trùng lặp (Correlation Penalty). Các thuật toán có tính tương quan quá cao sẽ bị loại (0 điểm). Do đó hệ thống cần tạo tín hiệu độc nhất.
  - Mục tiêu bắt buộc (Target Metrics): Sharpe $\ge$ 1.3, CAGR $\ge$ 15%, Max Drawdown $\ge$ -35%, Profit factor ≥ 1.3, Calmar ≥ 1.1

## 3. Kiến Trúc Luồng Chạy & Các Phân Hệ

### Pipeline Sinh Tự Động (`agent/` & Gốc)

- `main.py` (Thư mục gốc): Điểm neo khởi chạy hệ thống, chịu trách nhiệm thiết lập cấu hình cơ bản và ủy quyền (delegate) luồng sinh ý tưởng cho `agent/pipeline.py`.
- `agent/pipeline.py`: Trình điều khiển chính, hỗ trợ cả `Gemini` và `DeepSeek-Thinking`. Lặp qua các vòng: Gọi LLM sinh ý tưởng $\rightarrow$ Lưu JSON. Thiết kế tập trung vào việc tạo ra ý tưởng thô và tránh trùng lặp.
- `agent/convert_ideas.py`: Đóng vai trò bộ chuyển đổi trung gian từ định dạng JSON sang file Python hợp lệ (`SimpleAlgorithm`). Tích hợp logic xử lý ngoại lệ (anti-singularity) chống chia cho 0 và cơ chế Idempotent (Bỏ qua file đã chuyển đổi) để ngăn việc lặp lại.
- `agent/deepseek_client.py`: Client giao tiếp với API DeepSeek thông qua gói `deepseek4free`, tự động xử lý Cloudflare và xử lý stateful parsing để lấy dữ liệu suy luận (Thinking) chất lượng cao.
- `agent/gemini_client.py`: Giao diện gọi API ẩn danh Gemini.
- `agent/extract_json_response.py`: Tiện ích dùng chung để bóc tách dữ liệu JSON từ phản hồi của LLM (Regex Parser).
- `agent/portfolio.py`: Đánh giá các chỉ số tối thiểu (Sharpe, CAGR). Thực hiện cơ chế kiểm tra tương quan kép (Dual-Correlation).
- `agent/auto_submit.py` & `submit_all.py`: `agent/auto_submit.py` chứa logic mô phỏng thao tác Playwright/CDP tương tác với nền tảng Web. `submit_all.py` (tại thư mục gốc) là kịch bản đóng vai trò điểm quét các chiến lược mới và gọi tuần tự các API từ `auto_submit.py`.
- Tệp hỗ trợ (`agent/`): Các tệp như `prompts.py`, `validator.py`, `debug_response.py` cung cấp cấu trúc mẫu, đánh giá tính hợp lệ và hỗ trợ gỡ lỗi phản hồi cho pipeline chính.

### Sandbox Mocking (`xno_sdk/`)

- `emulator.py` $\rightarrow$ `XNOPlatformEmulator`: Khung kiểm thử (Testing Framework) được tinh chỉnh để mô phỏng chính xác cấu trúc biên dịch mã (AST parsing) của nền tảng XNOQuant Web. Xử lý triệt để việc loại bỏ từ khóa `import` nhằm đánh giá mã nguồn mà không gặp lỗi AST giả định.
- `series.py` $\rightarrow$ `RestrictedSeries`: Lớp bọc bảo vệ (wrapper) cho Pandas Series. Nó giới hạn quyền truy cập, loại bỏ các hàm bị cấm trong XNOQuant (như `.iloc`, `.mean()`) và chỉ cho phép các phương thức được whitelist (như `.where()`, `.fillna()`, `.ffill()`, `.pct_change()`, `.shift()`, `.diff()`).
- `engine.py`: Chứa `FeatureEngine` và `OperatorEngine` mô phỏng hành vi của sàn. Các hàm như `rolling_rank` được tinh chỉnh nhằm tăng cường tốc độ xử lý thông qua NumPy `sliding_window_view`.

### Core Engine (`backtest/`)

- `engine.py` $\rightarrow$ `XNOBacktestEngine.run()`: Nhận mảng vị thế từ chiến lược và mô phỏng giao dịch bar-by-bar, xử lý đóng/mở hợp đồng, trừ phí giao dịch theo tham số được cung cấp. Lệnh đầu tiên có trừ phí mở lệnh vào vốn ban đầu.
- `data_pipeline.py`: Xử lý, làm sạch và gắn nhãn phiên giao dịch cho dữ liệu gốc.
- `optimizer_v2.py` / `optimize_all_v2.py`: Hệ thống Tối ưu tham số thế hệ 2 sử dụng Optuna. Thay vì chèn tham số lúc chạy (phương pháp bị cấm trên Web), hệ thống sử dụng Regex để thay thế trực tiếp mã nguồn (Source Code Mutation). Hỗ trợ cơ chế Idempotent bằng cách gắn nhãn `# OPTIMIZATION_V2_COMPLETED`.
- `metrics.py`: Cung cấp bộ tính toán chỉ số hiệu năng (Sharpe, Sortino, VaR, CAGR, Max Drawdown). Được hiệu chỉnh nhằm cung cấp kết quả nhất quán với bộ tính toán của Web.

## 4. Liên Kết Hệ Thống (Workflow Khép Kín & Idempotent)

Quy trình tự động hóa được thiết kế theo cấu trúc 4 khối rời rạc, có khả năng chạy lại mà không tạo ra bản sao:

1. **Sinh Ý Tưởng (Generation)**: Khởi chạy từ điểm neo `main.py`, hệ thống ủy quyền cho mô-đun `agent/pipeline.py` quét cấu trúc kho lưu trữ nhằm loại bỏ các mẫu cũ, sau đó sử dụng LLM để xuất mã chiến lược dạng JSON vào thư mục `agent/results/ideas/`.
2. **Chuyển Đổi & Kiểm Thử Cục Bộ (Convert & Emulate)**: `agent/convert_ideas.py` diễn dịch chuỗi JSON thành Python AST (`.py`). Hệ thống `XNOPlatformEmulator` sẽ phân tích và loại bỏ các thành phần không tương thích. Các cấu trúc vượt qua được lưu vào `agent/results/`.
3. **Tối Ưu Hóa (Optimization)**: `optimize_all_v2.py` phân tích tham số linh hoạt, sử dụng Bayesian Search để dò tìm ngưỡng chỉ báo tối ưu. Ghi đè mã nguồn qua Regex và gắn nhãn trạng thái hoàn tất.
4. **Triển Khai Tự Động (Auto-Submit)**: `submit_all.py` sử dụng Playwright điều khiển giao diện trình duyệt để gửi mã nguồn lên `alpha.xnoquant.io`. Trích xuất dữ liệu trả về, báo cáo CSV và di chuyển tệp thành công vào `agent/results/pushed/` để loại khỏi chu kỳ sau.
