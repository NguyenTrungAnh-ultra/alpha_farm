# XNOQuant Auto-Gen Architecture

https://alpha.xnoquant.io/build
account: toinguyen15102004@gmail.com
password: anhtrung15102004

Dự án sinh chiến lược tự động.

## 1. Cấu trúc

- `agent/`: AI gen chiến lược. Gọi Gemini. Quản lý danh mục.
- `backtest/`: Core engine. Giả lập trade. Tính PnL/Fee. Xử lý dữ liệu.
- `strategies/`: Nơi chứa code chiến lược gen ra hoặc có sẵn.
- `XNOQuant/`: Chứa `strategies.py` (chiến lược nền tảng cũ).
- `run_backtest.py`: CLI chạy test đơn lẻ/tối ưu hóa.

## 2. Hàm & Luồng chạy

### Pipeline Sinh Tự Động (`agent/pipeline.py`)

- `run_pipeline()`: Tim mạch. Lặp n vòng. Gọi LLM sinh ý tưởng → Gen code → `validate_strategy` → `XNOBacktestEngine.run` → `portfolio.evaluate_and_add`.

### Agent & AI (`agent/`)

- `gemini_client.py` → `GeminiChat.send()`: Gọi API ẩn Gemini. Quản lý cookie, xoay vòng.
- `validator.py` → `validate_strategy()`: Chạy code LLM sinh ra. Bắt lỗi AST. Trả lại lỗi để LLM tự fix (`build_fix_prompt`).
- `portfolio.py` → `PortfolioManager.evaluate_and_add()`: Xét duyệt. Check Sharpe > 1.3, CAGR > 15%, MDD > -35%. Tính tương quan (`compute_max_correlation`). Đạt → Lưu đĩa.

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

Mô hình độc lập, full tự động.
