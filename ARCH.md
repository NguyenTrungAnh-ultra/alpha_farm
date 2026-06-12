# XNOQuant Auto-Gen Architecture

account: toinguyen15102004@gmail.com
password: anhtrung15102004

## 1. Cấu trúc Thư mục

- `agent/`: Chứa các kịch bản AI tạo chiến lược (gọi LLM API), quản lý danh mục và tự động nộp bài.
- `backtest/`: Động cơ (Engine) giả lập giao dịch nội bộ, cung cấp khả năng tính toán các chỉ số (PnL, Fee, Sharpe...) và hỗ trợ tối ưu hóa tham số.
- `xno_sdk/`: Thư viện giả lập môi trường Sandbox và các toán tử/chỉ báo của XNOQuant để hỗ trợ kiểm thử cục bộ.
- `strategies/`: Thư mục lưu trữ các chiến lược sinh ra.
- `XNOQuant/`: Bản lưu các chiến lược cũ.
- `run_backtest.py`: CLI chạy test đơn lẻ hoặc xác minh đối chiếu chéo.

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

### Pipeline Sinh Tự Động (`agent/pipeline.py`)

- `run_pipeline()`: Trình điều khiển chính. Lặp qua các vòng: Gọi LLM sinh ý tưởng $\rightarrow$ Sinh Code $\rightarrow$ `validate_strategy` $\rightarrow$ `XNOBacktestEngine.run` $\rightarrow$ `portfolio.evaluate_and_add`.

### Agent & AI (`agent/`)

- `gemini_client.py`: Gọi API ẩn danh Gemini.
- `validator.py`: Chạy thử đoạn code LLM sinh ra trong Sandbox nội bộ. Bắt các lỗi cú pháp AST và đưa lỗi lại cho LLM để tự sửa thông qua `build_fix_prompt`.
- `portfolio.py`: Đánh giá các chỉ số tối thiểu (Sharpe, CAGR). Thực hiện cơ chế kiểm tra tương quan kép (Dual-Correlation) trên cả chuỗi lợi nhuận và chuỗi tín hiệu để giảm thiểu chiến lược trùng lặp. Đạt đủ điều kiện thì lưu vào đĩa.
- `auto_submit.py`: Sử dụng Playwright và giao thức CDP để tự động dán mã chiến lược, mô phỏng trên nền tảng Web và xác nhận nộp bài. Script cũng có cơ chế bóc tách thông số (Metrics) trực tiếp từ giao diện DOM để lưu vào `leaderboard.csv`.

### Sandbox Mocking (`xno_sdk/`)

- `series.py` $\rightarrow$ `RestrictedSeries`: Lớp bọc bảo vệ (wrapper) cho Pandas Series. Nó giới hạn quyền truy cập, loại bỏ các hàm bị cấm trong XNOQuant (như `.iloc`, `.mean()`) và chỉ cho phép các phương thức được whitelist (như `.where()`, `.fillna()`, `.ffill()`, `.pct_change()`, `.shift()`, `.diff()`).
- `engine.py`: Chứa `FeatureEngine` và `OperatorEngine` mô phỏng hành vi của sàn. Các hàm như `rolling_rank` được tinh chỉnh tối ưu thời gian chạy cục bộ thông qua NumPy `sliding_window_view`.
- Cột `Volume` được chủ động lấp đầy bằng `fillna(0.0)` cho các vùng dữ liệu rỗng để phản ánh sát hơn dữ liệu của sàn.

### Core Engine (`backtest/`)

- `engine.py` $\rightarrow$ `XNOBacktestEngine.run()`: Nhận mảng vị thế từ chiến lược và mô phỏng giao dịch bar-by-bar, xử lý đóng/mở hợp đồng, trừ phí giao dịch theo tham số được cung cấp. Lệnh đầu tiên có trừ phí mở lệnh vào vốn ban đầu.
- `data_pipeline.py`: Xử lý, làm sạch và gắn nhãn phiên giao dịch cho dữ liệu gốc.
- `optimizer.py`: Tích hợp Optuna với phương pháp Bayesian Search để tìm tham số tối ưu cục bộ.
- `metrics.py`: Cung cấp bộ tính toán chỉ số hiệu năng (Sharpe, Sortino, VaR, CAGR, Max Drawdown). Hệ thống tính toán này được thiết kế dựa trên các công thức chuẩn hóa của Web XNOQuant nhằm giảm thiểu sai số đo lường.

## 4. Liên Kết Hệ Thống (Workflow)

1. **Khởi tạo**: Tải cấu hình, tải dữ liệu đa khung thời gian.
2. **Khởi tạo Ý tưởng**: LLM phân tích và đề xuất ý tưởng chiến lược.
3. **Sinh Code**: LLM viết mã tuân thủ luật XNOQuant.
4. **Kiểm tra**: Chạy `validator.py` để loại bỏ lỗi AST cục bộ.
5. **Tối ưu hóa**: Quét tham số thông qua `optimizer.py`.
6. **Mô phỏng (Backtest)**: Chạy chiến lược thông qua `XNOBacktestEngine`.
7. **Đánh giá & Lưu trữ**: Lọc qua `PortfolioManager` và lưu kết quả (Python script và CSV).
8. **Tự động Nộp bài**: Gọi `auto_submit.py` để mô phỏng chiến lược trên Web XNOQuant. Trích xuất Metrics vào Leaderboard CSV và chính thức nộp vào cuộc thi.
