# XNOQuant Auto-Gen Architecture

account: toinguyen15102004@gmail.com
password: anhtrung15102004

## 1. Cấu trúc Thư mục

- `agent/`: Chứa các kịch bản AI tạo chiến lược (gọi LLM API), quản lý danh mục, MCTS Engine và tự động nộp bài.
- `backtest/`: Động cơ (Engine) giả lập giao dịch nội bộ, cung cấp khả năng tính toán các chỉ số (PnL, Fee, Sharpe...) và hỗ trợ tối ưu hóa tham số.
- `xno_sdk/`: Thư viện giả lập môi trường Sandbox và các toán tử/chỉ báo của XNOQuant để hỗ trợ kiểm thử cục bộ.
- `agent/results/`: Thư mục lưu trữ các chiến lược sinh ra. Phân loại theo nguồn gốc (`llm_strategies` / `mcts_strategies`).

## 2. Hệ Thống Luật Chơi & Giới Hạn Của Sàn (XNOQuant Rules)

Dưới đây là các giới hạn và quy định chung để chiến lược có thể chạy được trên nền tảng `alpha.xnoquant.io`:

- **Khung thời gian (Universe):** Chỉ áp dụng cho hợp đồng tương lai VN30 (VN30F1M) ở các khung 1m, 3m, 5m, 10m, 15m, 30m, 60m.
- **Biến trạng thái vị thế:** Mục tiêu vị thế nằm trong dải `[-1, 1]`. Trong đó `1` = Full Long, `-1` = Full Short, `0` = Flat.
- **Nguồn dữ liệu hợp lệ:** Chỉ được phép gọi `self.data.pv_close`, `self.data.pv_volume`, và `self.data.pv_vn30_close`.
- **Luật Cấu trúc (Template Rules):**
  - Lớp chiến lược phải kế thừa `class CustomStrategy(SimpleAlgorithm)`.
  - Hàm thuật toán bắt buộc là `def __algorithm__(self):`. Không sử dụng hàm `__init__`.
  - Cấm sử dụng vòng lặp duyệt từng dòng (row-by-row). Code bắt buộc phải ở dạng Vectorized.
  - Thay vì để LLM tự do sinh mã dễ gây lỗi cú pháp (AST Error), hệ thống chuyển sang kiến trúc **Template-Based**. LLM chỉ sinh ra tham số dưới dạng JSON. Các tham số này được "ép" (clamped) vào các khoảng an toàn (Bounds) đã định nghĩa cứng trong các Template mẫu.
- **Quy trình tính điểm (Leaderboard):**
  - Điểm tổng của thí sinh dựa trên tính lũy kế (Cumulative). Nhiều chiến lược tốt sẽ tăng điểm tổng.
  - Sàn áp dụng hình phạt trùng lặp (Correlation Penalty). Các thuật toán có tính tương quan quá cao sẽ bị loại (0 điểm). Do đó hệ thống cần tạo tín hiệu độc nhất.
  - Mục tiêu bắt buộc (Target Metrics): Sharpe $\ge$ 1.3, CAGR $\ge$ 15%, Max Drawdown $\ge$ -35%, Profit factor ≥ 1.3, Calmar ≥ 1.1

## 3. Kiến Trúc Luồng Chạy & Các Phân Hệ

### MCTS Alpha Discovery Engine (`agent/`)

- `agent/mcts_engine.py`: Động cơ lõi sử dụng thuật toán Monte Carlo Tree Search. Tự động lắp ghép các thành phần toán học (toán tử, chỉ báo) thành Cây Cú Pháp Trừu Tượng (AST). Động cơ này áp dụng luật kiểm soát chiều không gian (Dimensional Consistency) cực kỳ nghiêm ngặt nhằm đảm bảo không cộng nhầm Giá với Khối Lượng.
- `agent/mcts_pipeline.py`: Chu trình tự động quét hàng ngàn biểu thức do MCTS sinh ra, dùng giả lập `XNOBacktestEngine` để đánh giá Sharpe, Return và Lọc bỏ những Alpha có tính tương quan (Correlation) quá cao với những file đã lưu trong `portfolio.json`. Ghi log số liệu vào `mcts_stats.json`.

### Pipeline LLM Sinh Tự Động & Tự Sửa Lỗi (`agent/`)

- `agent/pipeline.py`: Trình điều khiển chính của nhóm LLM, hỗ trợ `Gemini` (hiện tại là Gemini 3.1 Pro) và `DeepSeek`. Lặp qua các vòng: Gọi LLM sinh ý tưởng $\rightarrow$ Lưu tham số JSON. Thiết kế tập trung vào việc tạo ra ý tưởng. **Lưu ý:** Hệ thống vẫn giữ đầy đủ tùy chọn cho phép sử dụng Model Local (Ollama) làm bộ lập kế hoạch (Planner/Generator) chính.
- `agent/templates/`: Chứa `base_templates.py` và Registry. Hệ thống Template tĩnh này cung cấp bộ khung chuẩn xác về cú pháp và các giới hạn an toàn (Bounds) cho từng biến số, loại bỏ hoàn toàn việc phải sửa lỗi AST.
- `agent/optimize_ideas.py`: Vòng lặp tự tối ưu hóa tham số (Optuna Hyperparameter Tuning). Sau khi nhận tham số từ JSON, hệ thống chạy Backtest. Nếu mục tiêu không đạt (Sharpe > 1.3 và CAGR > 15%), hệ thống sẽ tự động kích hoạt thư viện `Optuna` để tối ưu hóa siêu tham số bằng toán học ngay lập tức (thử tối đa 20 lần) trước khi lưu hoặc bỏ vào `failed_conversions/`.
- `agent/convert_legacy_ideas.py`: Công cụ sử dụng mô hình Local (Ollama) đóng vai trò "Chuyên gia phân tích cấu trúc", tự động đọc các file JSON ý tưởng cũ (không có template) và ánh xạ vào Template phù hợp nhất.
- `agent/deepseek_client.py`, `gemini_client.py` & `ollama_client.py`: Giao diện gọi API. Riêng `ollama_client.py` có cơ chế tự bật/tắt server ẩn, hỗ trợ Model Local sinh ý tưởng hoặc phân tích cấu trúc ý tưởng cũ.
- `agent/portfolio.py`: Đánh giá các chỉ số tối thiểu (Sharpe, CAGR). Thực hiện cơ chế kiểm tra tương quan chéo (Cross-Correlation) giữa cả LLM và MCTS.
- `agent/auto_submit.py`: Đóng vai trò tự động nộp bài qua Playwright. Nó tự động đọc Meta-Tag `# [MCTS_DISCOVERY_ENGINE]` để gom file vào đúng thư mục (`pushed/llm_strategies/` hoặc `pushed/mcts_strategies/`).

### Sandbox Mocking & Core Engine (`xno_sdk/` & `backtest/`)

- `xno_sdk/emulator.py`: Khung kiểm thử được tinh chỉnh để mô phỏng chính xác trình biên dịch mã của nền tảng Web.
- `backtest/engine.py` $\rightarrow$ `XNOBacktestEngine.run()`: Nhận mảng vị thế từ chiến lược và mô phỏng giao dịch bar-by-bar, xử lý đóng/mở hợp đồng, trừ phí giao dịch. Tốc độ cực cao (Vectorized).
- `backtest/metrics.py`: Cung cấp bộ tính toán chỉ số hiệu năng (Sharpe, Sortino, VaR, CAGR, Max Drawdown).

## 4. Liên Kết Hệ Thống (Master Pipeline Dual Engine)

Quy trình tự động hóa được gộp thành hệ thống động cơ kép thông qua điểm neo **`agent/run_all.py`**, tích hợp sẵn **Menu Tương tác (Interactive CLI)** để chọn Model/Tham số và cơ chế **Fail-Fast** (dừng ngay lập tức khi có lỗi nghiêm trọng ở bất kỳ node nào). Hệ thống chạy tuần tự 5 Phase liên tục:

1. **Phase 1 (LLM Generation)**: Kích hoạt LLM (Gemini/DeepSeek) dựa trên Nhật ký (`experience_log.md`) để sinh ra các kịch bản ý tưởng (JSON).
2. **Phase 2 (Template Binding & Optuna Auto-Tuning)**: Nhận tham số JSON, "ép" vào Bounds của Template tĩnh. Đánh giá Sandbox cục bộ. Nếu mục tiêu không đạt (Sharpe > 1.3 và CAGR > 15%), thư viện `Optuna` sẽ tự động tìm kiếm bộ tham số tối ưu (tối đa 20 lần thử). Nếu đạt chuẩn, lưu vào danh mục chiến lược.
3. **Phase 3 (LLM Submit)**: Quét toàn bộ chiến lược của LLM, đẩy lên Web và dời file hoàn thành vào `agent/results/pushed/llm_strategies/`.
4. **Phase 4 (MCTS Discovery)**: Kích hoạt động cơ Monte Carlo Tree Search. MCTS tìm kiếm các tổ hợp toán học độc lạ, test tham số và sinh file mã trực tiếp. Các mã của MCTS được gán tự động Meta-Tag `# [MCTS_DISCOVERY_ENGINE]`.
5. **Phase 5 (MCTS Submit)**: Quét toàn bộ file có gắn Meta-Tag của MCTS và đẩy lên Web. Dời file thành công vào `agent/results/pushed/mcts_strategies/`.
