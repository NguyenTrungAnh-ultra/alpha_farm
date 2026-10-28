# Thiết kế — Bài cài tín hiệu (việc 3, kiểm soát dương RQ3)

Bản hiện hành. Đổi ý thì sửa đúng chỗ, kèm một dòng lý do + ngày.
Nguồn: proposal mục "Planted-Signal Test"; ROADMAP mục 2 việc 3.

Trạng thái: ⏸️ chờ người dùng duyệt các lựa chọn đánh dấu **[đề xuất]** (Claude đề xuất 2026-10-28).

## 1. Câu hỏi bài test trả lời

Nếu dữ liệu thật sự chứa một công thức mà ngữ pháp biểu diễn được, với độ mạnh IC biết trước, thì quy trình (MCTS trên bộ blueprint đã đóng băng) có tìm lại được không, và Sharpe ngoài mẫu đạt bao nhiêu? Không tìm lại được ở IC 0.05 ⇒ quy trình mù, phải sửa trước khi chạy walk-forward.

## 2. Dữ liệu

- **Khung và cửa sổ [đề xuất]:** 60m (tệp 1H không thiếu ngày, chạy nhanh). Dùng hình dạng cửa sổ walk-forward đầu tiên: tìm 2018-08-13 → 2020-06-30, đánh giá 2020-07-01 → 2020-12-31.
- **Nền placebo:** hoán vị lợi suất bar trong từng đoạn (tìm, đánh giá) như proposal. Mỗi bar mang theo Volume và hình dạng trong bar (Open/High/Low so với Close) của chính nó, rồi dựng lại giá từ lợi suất.
- **Cài tín hiệu [đề xuất]:** sinh tuần tự từng bar, vì công thức phụ thuộc giá mà giá lại phụ thuộc lợi suất đã cài:
  - `s_t = ts_zscore(A, W)` tính trên giá đã dựng tới bar t, với `A` là công thức cài;
  - `r_{t+1} = ε_{t+1} + β · σ_ε · s_t`, trong đó `ε` là lợi suất placebo đã hoán vị.
- **Hiệu chỉnh độ mạnh:** `β = IC / sqrt(1 − IC²)` cho tương quan Pearson mục tiêu. Đo lại IC Spearman thực tế (cùng định nghĩa `MCTSEngine.compute_rank_ic`) và báo cáo con số đo, không báo con số mục tiêu.
- **Độ mạnh:** IC = 0 (placebo thuần, đo tỷ lệ "tìm nhầm"), 0.01, 0.02, 0.05.

## 3. Công thức cài và blueprint

- **[đề xuất]** Sinh bộ blueprint một lần bằng `ollama-local` (20 ý tưởng, khung 60m) và đóng băng vào `results/planted/blueprints.json`. Bộ này dùng lại cho walk-forward.
- Chọn công thức cài sao cho **ít nhất một** blueprint trong bộ biểu diễn được nó, nhưng không trùng nguyên văn blueprint nào. Ứng viên mặc định: `sub(close, ts_mean(close, 20))` dưới template NORMALIZED. Ghi rõ blueprint nào chạm được công thức đó.
- Lý do: nếu không blueprint nào biểu diễn được công thức cài thì "không tìm lại" là do bộ blueprint chứ không do MCTS, bài test vô nghĩa.

## 4. Chạy

- MCTS trên đoạn tìm, rồi gộp top-5 trọng số đều, giao dịch trên đoạn đánh giá. Đây là đúng đơn vị đánh giá của proposal.
- **Ngân sách [đề xuất]:** 5.000 lượt lặp mỗi blueprint, 5 seed mỗi độ mạnh ⇒ 20 lượt chạy. Ước 20–40 phút trên máy này (chưa đo).
- Không chạy HMM: bài này không cần.

## 5. Đo và tiêu chí

**Kiểm tra "đáp án" trước khi chạy MCTS [đề xuất, thêm 2026-10-28 sau câu hỏi của người dùng về reward]:** chấm thẳng công thức cài bằng `MCTSEngine.evaluate_expression` trên đoạn tìm, ở từng độ mạnh. Lý do: reward có cổng cứng (−10 nếu Calmar < 1.1 hoặc < 15 lệnh). Nếu chính đáp án cũng nhận −10 thì reward không "cảm" được tín hiệu, và MCTS chỉ đang mò trong một mặt phẳng toàn −10. Khi đó lỗi nằm ở reward, không ở bước tìm. Ghi thêm tỷ lệ ứng viên nhận −10 trong mỗi lượt chạy.

**So hai bản reward (người dùng chốt 2026-10-28):** chấm đáp án bằng cả bản "gated" và bản "soft" (định nghĩa ở ROADMAP mục 3), ở IC 0 / 0.01 / 0.02 / 0.05. Chọn bản mà điểm đáp án tăng theo IC và tách khỏi điểm ở IC 0; nếu cả hai đều được thì chọn "soft" vì mặt reward mượt hơn cho MCTS. Lượt MCTS của bài này chạy với bản đã chọn; bản đó đóng băng cho walk-forward.

Mỗi (độ mạnh, seed) ghi:
- IC thực tế của tín hiệu cài trên đoạn tìm và đoạn đánh giá.
- **Tìm lại đúng:** có alpha trong top-5 có cùng cấu trúc và trường dữ liệu với công thức cài, cửa sổ lệch không quá một nấc trong `BASE_PERIODS` đã quy đổi.
- **Tìm lại gần:** tương quan Spearman giữa alpha tìm được và `A` trên đoạn tìm ≥ 0.7.
- Sharpe ngoài mẫu của chiến lược gộp trên đoạn đánh giá.

**Tiêu chí đạt [đề xuất, chốt trước khi chạy]:** ở IC 0.05, tìm lại gần ≥ 3/5 seed; ở IC 0, tìm lại gần ≤ 1/5 seed. IC 0.01 / 0.02 chỉ báo cáo, không đặt ngưỡng.

Kết quả: `results/planted/summary.csv` gồm các cột độ mạnh × {IC thực tế, tỷ lệ tìm lại đúng, tỷ lệ tìm lại gần, Sharpe ngoài mẫu trung bình ± độ lệch}.

## 6. Code (tên dự kiến)

- `strategy_workflows/PlantedSignal.py`: `permute_returns`, `build_ohlcv_from_returns`, `plant_signal`.
- `strategy_workflows/RunPlantedSignal.py` + lệnh `main.py planted`.
- Test bắt buộc:
  - hoán vị giữ nguyên tập lợi suất;
  - tín hiệu cài không nhìn trước tương lai: đổi `ε` sau bar t không đổi `s_≤t`;
  - IC thực tế nằm gần IC mục tiêu ở IC 0.05;
  - gộp top-5 dùng đúng trọng số đều.

## 7. Ngoài phạm vi

Vòng walk-forward đầy đủ, K = 19 placebo, cấu hình mốc, SPA/DSR (Tháng 2).
