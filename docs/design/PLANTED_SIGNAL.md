# Bài cài tín hiệu (kiểm soát dương, RQ2)

Phương pháp như đang dùng. Kết quả: [RESULTS](../RESULTS.md#bài-cài-tín-hiệu-hệ-thống-sinh-một-lần-bộ-blueprint-cũ). Quyết định: [DECISIONS](../DECISIONS.md#bài-cài-tín-hiệu). Các lần chạy trước: [log/2026-10_PLANTED_SIGNAL](../log/2026-10_PLANTED_SIGNAL.md). Code: `strategy_workflows/PlantedSignal.py`, `strategy_workflows/RunPlantedSignal.py`, mô tả ở [ARCH](ARCH.md) mục 3.4.

## Câu hỏi

Nếu dữ liệu chứa một công thức mà ngữ pháp biểu diễn được, với độ mạnh IC biết trước, thì quy trình (MCTS trên bộ blueprint đã đóng băng, chọn top-5 trên đoạn kiểm định) có tìm lại được không, và Sharpe ngoài mẫu đạt bao nhiêu? Kết quả báo dưới dạng **ngưỡng phát hiện**: IC nhỏ nhất mà quy trình tìm lại được, ứng với lượng dữ liệu và số công thức thử. Ngưỡng này chỉ áp cho tín hiệu kiểu như A, không suy rộng cho mọi tín hiệu.

## Dữ liệu

- Khung 60m (tệp 1H). Cách chia đoạn: đúng cửa sổ 1 của walk-forward (học / kiểm định / đánh giá), ghi ở `<out-dir>/segments.json`.
- **Nền placebo:** hoán vị lợi suất bar trong từng đoạn; mỗi bar mang theo Volume và hình dạng trong bar (Open/High/Low so với Close) của chính nó, rồi dựng lại giá từ lợi suất.
- **Cài tín hiệu:** sinh tuần tự từng bar, vì A phụ thuộc giá mà giá phụ thuộc lợi suất đã cài:
  - `s_t = ts_zscore(A, W)` tính trên giá đã dựng tới bar t;
  - `r_{t+1} = ε_{t+1} + β · σ_ε · s_t`, với `ε` là lợi suất placebo đã hoán vị.
- **Hiệu chỉnh độ mạnh:** tìm `β ≥ 0` bằng chia đôi sao cho IC Spearman trung bình trên 20 hoán vị hiệu chỉnh (seed 1001–1020) trên đoạn tìm bằng IC mục tiêu. Một β mỗi độ mạnh, dùng chung cho mọi seed và đoạn đánh giá. IC đo được của từng seed = mục tiêu + nhiễu mẫu; báo ở cả đoạn tìm và đoạn đánh giá.
- **Độ mạnh:** IC 0 (placebo thuần, đo tỷ lệ tìm nhầm), 0.05, 0.1. Seed 1–5; IC 0.1 thêm seed 6–10.

## Công thức cài A

- A được suy ra từ bộ blueprint đã đóng băng, không viết tay: đi theo thứ tự trong `blueprints.json`, lấy blueprint đầu tiên có ≥ 2 ô `?` và gốc NORMALIZED; mọi `?` → `close`, mọi cửa sổ = 10, cửa sổ z-score 10.
- Trùng nguyên văn một blueprint ⇒ lấy blueprint kế tiếp. A hằng trên nến tổng hợp ⇒ lấy blueprint kế tiếp. A có số hạng chết mà không hằng thì giữ (`ts_zscore` của chuỗi hằng trả 0).
- Không blueprint nào thoả ⇒ báo người dùng, không nới luật.
- Ít nhất một blueprint phải biểu diễn được A, nếu không thì "không tìm lại" là do bộ blueprint, không do quy trình.

## Chạy

- MCTS trên đoạn học, reward `sharpe`, 20 blueprint × 5.000 vòng.
- ≤ 100 biểu thức khác nhau tốt nhất → chấm lại trên đoạn kiểm định → top-5.
- Gộp vị thế top-5 trọng số đều, giao dịch trên đoạn đánh giá. Không chạy HMM.
- Lệnh: `main.py planted select|oracle|search|summary --out-dir … --search-start … --train-end … --search-end … --eval-end …`.

## Đo

- **Chấm đáp án** (`oracle`): chấm thẳng A bằng `MCTSEngine.evaluate_expression` trên đoạn tìm và đoạn học, ở từng độ mạnh, qua mọi ngưỡng z. Để biết reward có "cảm" được tín hiệu không. Lưu ý: cột `trades`, `calmar`, `rank_ic` của `oracle.csv` lấy từ ngưỡng z tốt nhất theo reward `soft` trên cả đoạn tìm, và ngừng đếm khi tài khoản bị gọi ký quỹ.
- **Tìm lại gần:** trong top-5 có công thức mà \|Spearman\| giữa giá trị thô của nó (trước z-score, ngưỡng, chiều của template) và giá trị thô của A trên cả đoạn tìm ≥ 0.7. Báo kèm phân bố tương quan.
- **Tìm lại đúng:** trong top-5 có công thức cùng cấu trúc và trường dữ liệu với A, NORMALIZED, cửa sổ và cửa sổ z lệch tối đa một nấc; gốc `sub` đổi chỗ là −A và chỉ tính với chiều −1.
- **Vị thế:** tương quan vị thế và tỷ lệ bar cùng dấu giữa từng ứng viên top-5 (tham số template của nó) và A (ngưỡng z, chiều tốt nhất trên đoạn học), trên đoạn tìm. Mức nền là các lượt IC 0.
- **Sharpe ngoài mẫu** của top-5 gộp trên đoạn đánh giá.
- Tỷ lệ lượt chấm lỗi (−10) mỗi lượt.

## Ngoài phạm vi

Nhiều công thức A có cùng IC mà quay vòng khác nhau (để tách tác động của IC với Sharpe sau phí của tín hiệu); khung phút.
