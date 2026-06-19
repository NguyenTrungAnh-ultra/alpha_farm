# XNOQuant Auto-Gen Architecture

> **Security Note:** Credentials have been moved to `.env` file. See `.env.example`.

## 1. Cấu trúc Thư mục Mới (Clean Architecture)

- `core_engine/`: Động cơ lõi, chứa Backtest Engine nội bộ và SDK Emulator giả lập môi trường XNOQuant.
- `llm_clients/`: Các module giao tiếp với API của AI (Gemini, DeepSeek, Ollama).
- `strategy_workflows/`: Quy trình tạo và xử lý chiến lược (Generate, MCTS, Portfolio, Validate, Submit).
- `utilities/`: Các tiện ích cấu hình tập trung (`AppConfig.py`), template và fixers.
- `results/`: Thư mục lưu trữ các chiến lược sinh ra. Phân loại theo nguồn gốc (`llm_strategies` / `mcts_strategies`).
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
  - Cấm sử dụng từ khóa `import` (numpy, pandas, talib). Mọi phép toán phải thông qua `self.feat` và `self.op`. (Hệ thống có bộ tự động nắn lại các phép toán Logic và phương thức gọi để tương thích với quy định này).
- **Quy trình tính điểm (Leaderboard):**
  - Điểm tổng của thí sinh dựa trên tính lũy kế (Cumulative). Nhiều chiến lược tốt sẽ tăng điểm tổng.
  - Sàn áp dụng hình phạt trùng lặp (Correlation Penalty). Các thuật toán có tính tương quan quá cao sẽ bị loại (0 điểm). Do đó hệ thống cần tạo tín hiệu độc nhất.
  - Mục tiêu bắt buộc (Target Metrics): Sharpe $\ge$ 1.3, CAGR $\ge$ 15%, Max Drawdown $\ge$ -35%, Profit factor ≥ 1.3, Calmar ≥ 1.1

## 3. Kiến Trúc Luồng Chạy & Các Phân Hệ

### MCTS Alpha Discovery Engine (`strategy_workflows/`)

- `MCTSEngine.py`: Động cơ lõi sử dụng thuật toán Monte Carlo Tree Search. Tự động lắp ghép các thành phần toán học (toán tử, chỉ báo) thành Cây Cú Pháp Trừu Tượng (AST). Động cơ này áp dụng luật kiểm soát chiều không gian (Dimensional Consistency) cực kỳ nghiêm ngặt nhằm đảm bảo không cộng nhầm Giá với Khối Lượng.
- `RunMCTS.py`: Chu trình tự động quét hàng ngàn biểu thức do MCTS sinh ra, dùng giả lập `BacktestEngine` để đánh giá Sharpe, Return và Lọc bỏ những Alpha có tính tương quan quá cao với những file đã lưu trong `portfolio.json`.

### Pipeline LLM Sinh Tự Động (`strategy_workflows/` & `llm_clients/`)

- `GenerateStrategies.py`: Trình điều khiển chính của nhóm LLM, hỗ trợ `Gemini` và `DeepSeek-Thinking`. Lặp qua các vòng: Gọi LLM sinh ý tưởng $\rightarrow$ Lưu JSON. Thiết kế tập trung vào việc tạo ra ý tưởng thô và tránh trùng lặp.
- `ConvertLegacyIdeas.py`: Đóng vai trò bộ chuyển đổi trung gian từ định dạng JSON sang file Python hợp lệ (`SimpleAlgorithm`).
- `llm_clients/`: Giao diện gọi API (`GeminiClient.py`, `DeepseekClient.py`, `OllamaClient.py`).
- `PortfolioManager.py`: Đánh giá các chỉ số tối thiểu (Sharpe, CAGR). Thực hiện cơ chế kiểm tra tương quan chéo (Cross-Correlation) giữa cả LLM và MCTS.
- `SubmitStrategies.py`: Đóng vai trò tự động nộp bài qua Playwright. Nó tự động đọc Meta-Tag `# [MCTS_DISCOVERY_ENGINE]` để gom file vào đúng thư mục.

### Sandbox Mocking & Core Engine (`core_engine/`)

- `PlatformEmulator.py`: Khung kiểm thử được tinh chỉnh để mô phỏng chính xác trình biên dịch mã của nền tảng Web.
- `BacktestEngine.py` $\rightarrow$ `XNOBacktestEngine.run()`: Nhận mảng vị thế từ chiến lược và mô phỏng giao dịch bar-by-bar, xử lý đóng/mở hợp đồng, trừ phí giao dịch. Tốc độ cực cao (Vectorized).
- `CalculateMetrics.py`: Cung cấp bộ tính toán chỉ số hiệu năng (Sharpe, Sortino, VaR, CAGR, Max Drawdown).

## 4. Liên Kết Hệ Thống (Master Pipeline Dual Engine)

Quy trình tự động hóa được gộp thành hệ thống động cơ kép thông qua CLI Master Controller **`main.py`** với thư viện `argparse`. Hệ thống có thể chạy từng module độc lập hoặc chạy chuỗi tuần tự liên tục (Pipeline):

1. **Phase 1 (LLM Generation)**: Kích hoạt LLM (Gemini/DeepSeek) sinh ý tưởng (`python main.py generate`).
2. **Phase 2 (Convert & Validate)**: Phân tích JSON thông qua AST NodeTransformer. Loại bỏ các lệnh bị cấm và giả lập hộp cát (`python main.py convert`).
3. **Phase 3 (Optimization)**: Chạy Optuna Bayesian Tuning tìm ra thông số tối ưu nhất cho từng chiến lược (`python main.py optimize`).
4. **Phase 4 (Auto Submit)**: Quét toàn bộ chiến lược thành công, đẩy lên Web và dời file hoàn thành vào `results/pushed/` (`python main.py submit`).

## 5. Hệ Thống Phân Loại & Sửa Lỗi Sandbox

Khi `strategy_workflows/CorrectFailedIdeas.py` xử lý một idea thất bại, lỗi được phân vào 4 tầng:

| Tầng | Loại lỗi | Xử lý | Module |
|------|----------|-------|--------|
| 1 | **Cú pháp Python** — SyntaxError, IndentationError | ✅ Tự sửa (Regex + AST) | `SandboxPrefixer.py` |
| 2a | **NameError / API sai** — `rolling_max` không có prefix, `self.param_xxx`, `np.abs`, `&&` | ✅ Tự sửa (Regex) | `SandboxPrefixer.py` |
| 2b | **API sai không phát hiện được** — sai thứ tự tham số, gọi hàm không tồn tại | ⚙️ LLM self-correction (3 attempts) | `CorrectFailedIdeas.py` |
| 3 | **Runtime Error** — ZeroDivision, NaN/Inf, TypeError | ⚙️ LLM self-correction (3 attempts) | `CorrectFailedIdeas.py` |
| **4** | **Logic tài chính kém** — Sharpe < 1.3 (code chạy nhưng chiến lược dở) | ⏭ **BỎ QUA** — không retry LLM | — |

### Ghi chú Tầng 4 (Bỏ qua, không auto-fix)

- **Nguyên nhân thường gặp**: Tín hiệu entry/exit ngược chiều, tautology (`exit = close != close`), tham số quá agressive, quá nhiều trade (fee ăn hết lợi nhuận), không bao giờ vào lệnh (`n_trades = 0`).
- **Lý do không auto-fix**: Sửa được cú pháp không đồng nghĩa cải thiện được Sharpe. Cần tái sinh idea mới từ MCTS hoặc LLM generation.
