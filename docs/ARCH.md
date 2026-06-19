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

- `MCTSDimensions.py`: Nơi đăng ký mọi Toán tử và quy tắc chữ ký hàm (Arity). Hệ thống áp dụng triết lý **Component Splitting** (phân rã các chỉ báo Tuple như MACD, BBANDS thành các mảng 1D độc lập) và đưa các chỉ báo nhiều tham số tĩnh (như VWAP, ADX) về Arity 0 (Terminal Nodes) để đảm bảo LLM và MCTS không bao giờ điền sai tham số.
- `SemanticCompiler.py`: Bộ biên dịch AST thông minh. Không chỉ kiểm tra cú pháp, bộ biên dịch còn thực thi nghiêm ngặt luật chống **Dimensional Bleeding** (Rò rỉ thứ nguyên) để ngăn chặn việc cộng/trừ các đơn vị Giá với Khối lượng hoặc RSI, hủy ngay lập tức các nhánh vô nghĩa về mặt vật lý tài chính.
- `MCTSEngine.py`: Động cơ lõi sử dụng thuật toán Monte Carlo Tree Search. Tự động lắp ghép các thành phần toán học dựa trên sự cho phép của `SemanticCompiler`. Động cơ tự động tiêm chính xác các tham số cửa sổ (như `timeperiod` hay `periods`) vào đúng hàm.
- `RunMCTS.py`: Chu trình quét hàng ngàn biểu thức do MCTS sinh ra, dùng giả lập `BacktestEngine` (được giới hạn data từ 2020-2023 để tiết kiệm tài nguyên) để đánh giá Sharpe, Return và lọc bỏ những Alpha có tính tương quan quá cao với những file đã lưu trong `portfolio.json`.

### Pipeline LLM Sinh Tự Động (`strategy_workflows/` & `llm_clients/`)

- `GenerateStrategies.py`: Trình điều khiển chính của nhóm LLM (Gemini, DeepSeek, Ollama). Nhiệm vụ sinh ra **Macro-Blueprint** chứa cấu trúc chiến lược dạng khung (chứa các dấu `?`). Đặc biệt, tiến trình này nhúng sẵn bộ `SemanticCompiler` để chặn đứng các lỗi cú pháp và lỗi ảo giác (hallucination) ngay lúc sinh mã, đẩy mô hình vào vòng lặp Self-Correction trước khi lưu file JSON.
- `SemanticCompiler.py`: Bộ biên dịch AST thông minh. Có khả năng "Auto-pad" (đệm tham số còn thiếu), "Auto-fold" (gộp cụm logic) và có bộ từ điển `HALLUCINATION_MAP` để ép các hàm do LLM "bịa ra" về đúng chuẩn hàm của nền tảng.
- `llm_clients/`: Giao diện gọi API (`GeminiClient.py`, `DeepseekClient.py`, `OllamaClient.py`).
- `PortfolioManager.py`: Đánh giá các chỉ số tối thiểu (Sharpe, CAGR). Thực hiện cơ chế kiểm tra tương quan chéo (Cross-Correlation) giữa các chiến lược.
- `SubmitStrategies.py`: Đóng vai trò tự động nộp bài qua Playwright. Nó tự động nộp các chiến lược Python đã qua bước Sandbox.

### Sandbox Mocking & Core Engine (`core_engine/`)

- `PlatformEmulator.py`: Khung kiểm thử được tinh chỉnh để mô phỏng chính xác trình biên dịch mã của nền tảng Web.
- `BacktestEngine.py` $\rightarrow$ `XNOBacktestEngine.run()`: Nhận mảng vị thế từ chiến lược và mô phỏng giao dịch bar-by-bar, xử lý đóng/mở hợp đồng, trừ phí giao dịch. Tốc độ cực cao (Vectorized).
- `CalculateMetrics.py`: Cung cấp bộ tính toán chỉ số hiệu năng (Sharpe, Sortino, VaR, CAGR, Max Drawdown).

## 4. Liên Kết Hệ Thống (Master Pipeline 3 Tầng)

Quy trình tự động hóa được chia làm 3 tầng (3-Tier Architecture) thông qua CLI Master Controller **`main.py`** với thư viện `argparse`:

1. **Phase 1 (LLM Blueprint Generation)**: LLM (Gemini/DeepSeek/Ollama) viết kịch bản dạng khung Macro-Blueprint. `SemanticCompiler` sẽ xác thực AST và ép LLM tự sửa các lỗi cú pháp ngay tại vòng lặp (`python main.py generate`).
2. **Phase 2 (MCTS Brute-force & Compile)**: Động cơ MCTS nạp các Blueprint, nhét các tham số hợp lệ vào các điểm `?`, biên dịch thành mã Python và chạy giả lập Backtest Sandbox để kiểm tra Sharpe (`python main.py mcts`).
3. **Phase 3 (Auto Submit)**: Quét toàn bộ chiến lược thành công, đẩy lên Web và dời file hoàn thành vào `results/pushed/` (`python main.py submit`).

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
