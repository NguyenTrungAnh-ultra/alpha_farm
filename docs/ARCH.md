# Alpha Farm Architecture

> **Security Note:** Credentials have been moved to `.env` file. See `.env.example`.

## 1. Cấu trúc Thư mục Hệ thống (Clean Architecture)

- `core_engine/`: Động cơ lõi, chứa AlphaBacktestEngine nội bộ, module AlphaPrimitives và AlphaEngine điều phối.
- `llm_clients/`: Các module giao tiếp với API của AI (Gemini, DeepSeek, Ollama).
- `strategy_workflows/`: Quy trình tạo và xử lý chiến lược (Generate, MCTS, Portfolio, HMM Validate).
- `utilities/`: Các tiện ích cấu hình tập trung (`AppConfig.py`), template và logger.
- `data/`: Thư mục chứa dữ liệu tĩnh và các bộ nhớ đệm giả lập như Monte Carlo Cache (`MCdata/`).
- `results/`: Thư mục lưu trữ các chiến lược sinh ra và danh mục tổng hợp (Portfolio).
- `docs/`: Chứa các tài liệu kỹ thuật chi tiết như ARCH.md.
- `tests/`: Thư mục chứa bộ kiểm thử đơn vị tự động bao trùm toàn bộ hệ thống (Pytest).

## 2. Hệ Thống Luật & Giới Hạn Thi Hành (Execution Rules)

Dưới đây là các giới hạn và quy định chung để chiến lược có thể chạy mượt mà trên `AlphaBacktestEngine`:

- **Khung thời gian (Universe):** Áp dụng cho hợp đồng tương lai VN30 (VN30F1M) ở các khung intraday.
- **Biến trạng thái vị thế:** Mục tiêu vị thế nằm trong dải `[-1, 1]`. Trong đó `1` = Full Long, `-1` = Full Short, `0` = Flat.
- **Nguồn dữ liệu hợp lệ:** Chỉ được phép gọi `self.data.pv_close`, `self.data.pv_volume`, và `self.data.pv_vn30_close`, v.v... qua `AlphaDataProxy`.
- **Luật Cấu trúc (AST Rules):**
  - Lớp chiến lược phải kế thừa `class AlphaStrategy`.
  - Hàm thuật toán bắt buộc là `def __algorithm__(self):`. Không sử dụng hàm `__init__`.
  - Cấm sử dụng vòng lặp duyệt từng dòng (row-by-row). Code bắt buộc phải ở dạng Vectorized thông qua `AlphaPrimitives` (như `ts_mean`, `ts_corr`).
  - Hệ thống tự động nắn lại các phép toán Logic và phương thức gọi bằng `SemanticCompiler`.
- **Quy trình tính điểm nội bộ:**
  - Mục tiêu bắt buộc (Target Metrics): Sharpe $\ge$ 1.3, CAGR $\ge$ 15%, Max Drawdown $\ge$ -35%, Profit factor ≥ 1.3, Calmar ≥ 1.1

## 3. Kiến Trúc Luồng Chạy & Các Phân Hệ

### MCTS Alpha Discovery Engine (`strategy_workflows/`)

- `MCTSDimensions.py`: Nơi đăng ký mọi Toán tử và quy tắc chữ ký hàm (Arity). Hệ thống áp dụng 9 Primitives cốt lõi thay vì hàng loạt chỉ báo kỹ thuật rời rạc. 
- `SemanticCompiler.py`: Bộ biên dịch AST thông minh. Không chỉ kiểm tra cú pháp, bộ biên dịch còn thực thi nghiêm ngặt luật chống **Dimensional Bleeding** (Rò rỉ thứ nguyên). Có bộ từ điển `HALLUCINATION_MAP` để ép các hàm bịa ra từ LLM (`sma`, `boll`) về chuẩn Primitives (`ts_mean`).
- `MCTSEngine.py`: Động cơ lõi sử dụng thuật toán Monte Carlo Tree Search. Tích hợp Máy chém Calmar (Hard Filter) và tính toán phần thưởng Đa mục tiêu. Hệ thống tích hợp **Scale-Mismatch Logic** để các chu kỳ luôn nội suy chuẩn xác khi chuyển đổi Timeframe.
- `RunMCTS.py`: Tiến trình Worker (Chạy đa luồng). Ngay khi khởi động, nó nạp Ma trận Vị thế lịch sử (Ký ức toàn cục) từ `portfolio_summary.json` và truyền vào MCTS để chống đạo nhái (Correlation Penalty). `RunMCTS.py` thực hiện Nghiệm thu một chạm (One-pass Commit): lấy đúng 1 chiến lược Top 1 và lưu.
- `HMMValidation.py`: (Tích hợp sâu vào MCTS) 3-Tier Realistic Validation, lọc chiến lược qua các kịch bản nhiễu loạn Monte Carlo của Hidden Markov Model, Kelly Fraction và Benchmark thực tế.

### Pipeline LLM Sinh Tự Động (`strategy_workflows/` & `llm_clients/`)

- `GenerateStrategies.py`: Trình điều khiển chính của nhóm LLM (Gemini, DeepSeek, Ollama). Nhiệm vụ sinh ra **Macro-Blueprint** chứa cấu trúc chiến lược dạng khung (chứa các dấu `?`). Đặc biệt, tiến trình này nhúng sẵn bộ `SemanticCompiler` để chặn lỗi cú pháp và lỗi ảo giác, ép LLM vào vòng lặp Self-Correction trước khi lưu file JSON.
- `llm_clients/`: Giao diện gọi API (`GeminiClient.py`, `DeepseekClient.py`, `OllamaClient.py`).
- `PortfolioManager.py`: Sổ cái lưu trữ và quản lý danh mục (Portfolio Ledger). Ở kiến trúc mới (One-pass), các bài kiểm tra rủi ro đã được đẩy vào `MCTSEngine`. MCTS lưu chiến lược thông qua cờ `force_add=True`.

### Động Cơ Lõi Siêu Tốc (Vectorized `core_engine/`)

- `AlphaPrimitives.py`: Trái tim toán học của hệ thống. Chứa các hàm (như `ts_mean`, `ts_zscore`, `ts_rank`) được viết bằng `np.lib.stride_tricks.sliding_window_view`, đạt tốc độ xử lý nhanh hơn từ 15x đến hàng trăm lần so với các hàm `pandas.rolling()`.
- `AlphaBacktestEngine.py`: Động cơ mô phỏng giao dịch bar-by-bar siêu tốc (**Vectorized Numpy**). Tích hợp cơ chế **VN30F Netting Fee**, thuật toán khóa rò rỉ dữ liệu (Lookahead Bias) bằng lệnh `shift(1)` vị thế, và hệ thống **Vectorized Margin Call** ngăn chặn cháy tài khoản âm. Mới đây nhất, động cơ được bổ sung **Vectorized Rollover Penalty** tại các phiên ATC ngày đáo hạn, ép MCTS tính toán đúng chi phí trượt giá.
- `CalculateMetrics.py`: Cung cấp bộ tính toán chỉ số hiệu năng (Sharpe, Sortino, VaR, CAGR, Max Drawdown).
- `AlphaEngine.py`: Lớp Wrapper cấp cao (Facade) gom `AlphaBacktestEngine`, `CalculateMetrics` và `AlphaDataProxy` để thực thi chiến lược.

### Testing & Environment (`tests/` & `uv`)
- Môi trường dự án được khóa chặt ở **Python 3.12** sử dụng **`uv`** để tối ưu hóa tốc độ build các thư viện gốc C++.
- Khung kiểm thử sử dụng **`pytest`** bao phủ các module lõi (`core_engine`, `strategy_workflows`, `hardware_concurrency`) đạt điểm Pass 100%.

## 4. Liên Kết Hệ Thống (Master Pipeline 2 Tầng)

Quy trình tự động hóa được điều khiển thông qua CLI Master Controller **`main.py`** với thư viện `argparse`:

1. **Phase 1 (LLM Blueprint Generation)**: LLM viết kịch bản dạng khung Macro-Blueprint. `SemanticCompiler` sẽ xác thực AST và ép LLM tự sửa các lỗi cú pháp ngay tại vòng lặp (`python main.py generate`).
2. **Phase 2 (MCTS Brute-force & Compile)**: Động cơ MCTS nạp các Blueprint, nhét các tham số hợp lệ vào các điểm `?`, biên dịch thành mã Python chứa `AlphaPrimitives` và chạy giả lập trên `AlphaBacktestEngine` để đánh giá mảng đa mục tiêu (`python main.py mcts`). Lọc top và lưu thẳng vào Portfolio.

---

## 5. Hệ Thống Phân Loại & Sửa Lỗi (Inline Self-Correction)

Thay vì sửa lỗi bằng kịch bản rời rạc, mọi thứ được ép thẳng vào đường ống:

### 5.1. Vòng Lặp Self-Correction Trong Quá Trình Sinh Ý Tưởng
Khi `GenerateStrategies.py` yêu cầu LLM tạo Macro-Blueprint, mã JSON sinh ra sẽ bị kiểm tra ngay:
- **Macro-Blueprint Semantic Error**: Lỗi được bắt bởi `SemanticCompiler.py`. Dữ liệu lỗi được gửi lại vào LLM để tự sửa (Max retry = 3). 
- **Mapping (Ảo giác LLM)**: Các Indicator truyền thống như `sma` hoặc `bollinger_band_upper` sẽ bị `HALLUCINATION_MAP` bẻ lái sang `ts_mean` để ép tương thích.

### 5.2. MCTS Sandboxing
- Các công thức sinh ra lỗi toán học (ZeroDivision, NaN/Inf) hoặc đạt Sharpe < 1.3, Calmar < 1.1 sẽ bị hệ thống **MCTS Máy chém** chém ngay lập tức (Reward = -10.0), ép cây tìm kiếm đi nhánh khác. Thao tác này tiết kiệm thời gian hơn nhiều so với việc bắt LLM sửa lại một công thức vô dụng.
