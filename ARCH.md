# XNOQuant Auto-Gen Architecture

https://alpha.xnoquant.io/build
account: toinguyen15102004@gmail.com
password: anhtrung15102004

Dự án sinh chiến lược tự động.

## 1. Cấu trúc

- `agent/`: AI gen chiến lược, gọi Gemini API, quản lý danh mục và tự động nộp bài.
- `backtest/`: Core engine giả lập giao dịch, tính toán các chỉ số (PnL, Fee, Sharpe...) và tối ưu hóa tham số.
- `xno_sdk/`: Thư viện giả lập môi trường Sandbox và các toán tử/chỉ báo của XNOQuant cục bộ.
- `strategies/`: Các file chiến lược python mẫu và mới được tạo ra.
- `XNOQuant/`: Bản lưu các chiến lược cũ trên web.
- `run_backtest.py`: CLI chạy test đơn lẻ/tối ưu hóa.

## 2. Hàm & Luồng chạy

### Pipeline Sinh Tự Động (`agent/pipeline.py`)

- `run_pipeline()`: Tim mạch. Lặp n vòng. Gọi LLM sinh ý tưởng → Gen code → `validate_strategy` → `XNOBacktestEngine.run` → `portfolio.evaluate_and_add`.

### Agent & AI (`agent/`)

- `gemini_client.py` → `GeminiChat.send()`: Gọi API ẩn Gemini. Quản lý cookie, xoay vòng.
- `validator.py` → `validate_strategy()`: Chạy code LLM sinh ra. Bắt lỗi AST. Trả lại lỗi để LLM tự fix (`build_fix_prompt`).
- `portfolio.py` → `PortfolioManager.evaluate_and_add()`: Xét duyệt. Check Sharpe > 1.3, CAGR > 15%, MDD > -35%. Tính tương quan (`compute_max_correlation`). Đạt → Lưu đĩa.
- `auto_submit.py` → `run_auto_submit()`: Nạp code chiến lược đã được format sạch (CustomStrategy), chạy giả lập trên web và tự động nộp vào cuộc thi VQC 2026. Có cơ chế dự phòng tự động khởi chạy trình duyệt và đăng nhập bằng thông tin trong `ARCH.md` nếu CDP port 9222 bị từ chối.

### Sandbox Mocking (`xno_sdk/`)

- `series.py` → `RestrictedSeries`: Bọc `pd.Series` của Pandas để chặn các thuộc tính/phương thức cấm trong sandbox (`.mean()`, `.std()`, `.iloc`, physical indexing) và whitelist các phương thức hợp lệ trên sàn (`.where()`, `.fillna()`, `.ffill()`, `.pct_change()`, `.shift()`, `.diff()`, `.astype()`).
- `engine.py` → `FeatureEngine` & `OperatorEngine`: Định nghĩa toàn bộ 30 toán tử và chỉ báo tùy chỉnh tương thích 100% với hệ thống XNOQuant. Tính năng `rolling_rank` được tăng tốc 360 lần bằng thuật toán Vectorized NumPy `sliding_window_view`.
- `engine.py` → `DataProxy`: Giả lập mảng `pv_volume` cố định về toàn bộ `0.0` để mô phỏng chính xác lỗi dữ liệu khối lượng bị rỗng trên web.

### Core Engine (`backtest/`)

- `engine.py` → `XNOBacktestEngine.run()`: Nhận vector vị thế (`strategy.run_algorithm`). Duyệt từng bar. Đóng/Mở hợp đồng. Trừ phí (`fee_per_contract`). Trả `BacktestResult`.
- `engine.py` → `load_data()`: Load CSV.
- `data_pipeline.py` → `prepare()`: Gộp `load()`, `clean()`, `tag_sessions()`. Cắt bar rỗng. Phân loại sáng/chiều.
- `optimizer.py` → `Optimizer.run()`: Bayesian search (Optuna) tìm tham số ngon.
- `metrics.py` / `reporting.py`: In bảng. Vẽ biểu đồ equity.

### Tương tác CLI (`run_backtest.py` & `runner.py`)

- `run_backtest.py` → `main()`: Parse arg. Gọi `optimize()` hoặc `run_single()` cho `sma_crossover`.
- `runner.py` → `run_verification()`: Test chéo kết quả Engine Local vs Engine Web XNOQuant.

## 3. Liên kết Hệ Thống

1. **Khởi tạo**: `run_pipeline` load cookie, load data 5 khung giờ.
2. **Gen Idea**: `pipeline` gọi `GeminiChat.send_json(idea_prompt)`.
3. **Gen Code**: `pipeline` gọi `GeminiChat.send(code_prompt)`.
4. **Validate**: Chạy code qua `validator.py`. Lỗi → Vòng lặp tự fix (max 3 lần).
5. **Optimize**: Truyền code pass vào `Optimizer`. Bayesian 100 trials.
6. **Backtest**: `Optimizer` gọi `XNOBacktestEngine.run()`.
7. **Filter**: Đẩy `BacktestResult` qua `PortfolioManager`. Check constraints.
8. **Save**: Lưu `{name}_{tf}.py` và `{name}_{tf}_equity.csv`.
9. **Auto Submit**: Gọi `run_auto_submit()` để đẩy thẳng chiến lược đạt chuẩn lên web XNOQuant và đăng ký vào cuộc thi VQC 2026.

Mô hình độc lập, full tự động.
