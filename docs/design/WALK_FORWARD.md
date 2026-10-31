# Walk-forward trên dữ liệu thật

Phương pháp như đang dùng. Trạng thái từng bước: [PLAN](../PLAN.md). Quyết định: [DECISIONS](../DECISIONS.md#walk-forward). Quá trình thiết kế: [log/2026-10_WALK_FORWARD](../log/2026-10_WALK_FORWARD.md). Code: `strategy_workflows/WalkForward.py`, `main.py walkforward placebo|freeze|real|summary`, mô tả ở [ARCH](ARCH.md) mục 3.5.

## Câu hỏi

Chạy quy trình tìm alpha như thể đứng ở từng thời điểm trong quá khứ: chỉ thấy dữ liệu trước thời điểm đó, chọn top-5, giao dịch 6 tháng kế tiếp. Ghép các đoạn 6 tháng thành một chuỗi lợi suất ngày ngoài mẫu 2022-07 → 2025-12. Sharpe năm của chuỗi đó là thước đo chính cho RQ1 và RQ2.

## Cửa sổ

Nở dần từ 2018-08-13, khung 60m (tệp 1H). Đoạn kiểm định 12 tháng ngay trước đoạn đánh giá (đề xuất của Claude, chưa chốt riêng); đoạn học là toàn bộ phần trước đó.

| Cửa sổ | Học tới | Kiểm định | Đánh giá |
|---|---|---|---|
| 1 | 2021-06-30 | 2021-07 → 2022-06 | 2022-07 → 2022-12 |
| 2 | 2021-12-31 | 2022-01 → 2022-12 | 2023-01 → 2023-06 |
| 3 | 2022-06-30 | 2022-07 → 2023-06 | 2023-07 → 2023-12 |
| 4 | 2022-12-31 | 2023-01 → 2023-12 | 2024-01 → 2024-06 |
| 5 | 2023-06-30 | 2023-07 → 2024-06 | 2024-07 → 2024-12 |
| 6 | 2023-12-31 | 2024-01 → 2024-12 | 2025-01 → 2025-06 |
| 7 | 2024-06-30 | 2024-07 → 2025-06 | 2025-07 → 2025-12 |

Số bar từng đoạn: [RESULTS](../RESULTS.md#dữ-liệu). Độ nhạy của cửa sổ yếu nhất (cửa sổ 1) đo bằng [bài cài tín hiệu](PLANTED_SIGNAL.md).

## Mỗi cửa sổ

1. MCTS trên đoạn học, reward `sharpe`, 20 blueprint × 5.000 vòng (100.000 lượt chấm).
2. ≤ 100 biểu thức khác nhau tốt nhất → chấm lại trên đoạn kiểm định → top-5.
3. Vị thế top-5 trọng số đều, giao dịch trên đoạn đánh giá (phí, ký quỹ như `AlphaBacktestEngine`); lịch sử chỉ báo lấy từ khung liên tục.
4. Ghi lợi suất ngày của đoạn đánh giá, top-5 (biểu thức + tham số template + chiều), reward học / kiểm định.
5. 5 seed (1–5) mỗi cấu hình.

Lợi suất ngày = chênh lệch vốn cuối ngày chia vốn ban đầu; Sharpe = trung bình / độ lệch (ddof 0) × √252.

## Cấu hình so sánh

Cùng ngân sách 100.000 lượt chấm mỗi cửa sổ, cùng bước 2–4. Cách làm các dòng chưa code là đề xuất, chờ duyệt.

| Cấu hình | Cách làm | RQ | Code |
|---|---|---|---|
| LLM + MCTS | như mục trên | 1, 2 | ✅ |
| MCTS không có LLM | MCTS từ gốc là một ô `?` dưới template NORMALIZED, 100.000 vòng | 1 | ⛔ |
| LLM không tìm | LLM viết công thức hoàn chỉnh (không `?`); chấm hết số LLM viết được, ghi rõ ngoại lệ về ngân sách | 1 | ⛔ |
| Tìm ngẫu nhiên | 100.000 công thức hợp lệ về chiều, sinh ngẫu nhiên đều theo ngữ pháp | 1 | ⛔ |
| Mua và giữ | luôn long | tham chiếu | ⛔ |
| TSMOM | momentum chuỗi thời gian (Moskowitz 2012), chuyển sang bar trong ngày | tham chiếu | ⛔ |

**Độ chênh Sharpe phát hiện được** (877 ngày = 3,48 năm; Memmel 2003, một phía α = 0.05): sai số chuẩn của chênh lệch = √((2 − 2ρ + ½(SR₁² + SR₂² − 2ρ²SR₁SR₂)) / 3,48), ρ là tương quan lợi suất ngày giữa hai cấu hình (chưa đo, chờ lần chạy thật). Chênh tối thiểu với power 50% / 80% (SR₁ = 1, SR₂ = 0): ρ = 0 ⇒ 1.39 / 2.11; ρ = 0.3 ⇒ 1.22 / 1.84; ρ = 0.5 ⇒ 1.08 / 1.63; ρ = 0.7 ⇒ 0.92 / 1.40. Một Sharpe đơn lẻ có sai số chuẩn 0.54 (placebo đo được 0.51).

## Placebo

- Lặp toàn bộ walk-forward của LLM + MCTS trên K = 19 bộ placebo: hoán vị lợi suất trong từng đoạn (học, kiểm định, đánh giá xáo riêng), mỗi cửa sổ một bản hoán vị riêng, seed = 100000 + 100·k + w.
- Một seed MCTS (seed 1) mỗi bộ. Bộ placebo có Sharpe NaN không tính vào K.
- p = (1 + số bộ placebo có Sharpe ≥ lần thật) / (K + 1); nhỏ nhất 0.05.

## Đóng băng

`main.py walkforward freeze` ghi `results/walkforward/frozen.json`: reward + `REWARD_WEIGHTS`, bảng cửa sổ, tệp blueprint (sha256), ngân sách, seed, khung, `MAX_RANKED`, `TOP_K`, commit git, dấu vân tay dữ liệu. `real` từ chối chạy nếu bất kỳ trường nào khác bản đóng băng, hoặc `git diff --name-only <commit đóng băng>` trên `main.py`, `core_engine/`, `strategy_workflows/`, `utilities/` không rỗng. Vì thế mọi code (kể cả cấu hình so sánh) phải xong trước khi đóng băng.

## Bộ blueprint

Bộ đóng băng: `results/blueprint_sets/20261029_212813/`. Tiêu chí bộ thật: 0 blueprint trùng nguyên văn ví dụ trong prompt; không hai blueprint cùng khung (so cấu trúc cây, bỏ qua tên trường điền sẵn); mọi blueprint có ≥ 1 `?` và biên dịch được; `qwen3.5:4b`, 20 blueprint. Số liệu của bộ: [RESULTS](../RESULTS.md#bộ-blueprint).

## Thời gian máy

Ước trước khi tăng tốc backtest, chưa đo lại (một lượt bài cài tín hiệu cửa sổ 1 nhanh gần gấp đôi sau tăng tốc):

| Phần | Lượt | Ước |
|---|---|---|
| LLM + MCTS | 7 cửa sổ × 5 seed = 35 | ≈ 4 giờ |
| MCTS không LLM, tìm ngẫu nhiên | 2 × 35 = 70 | ≈ 8 giờ |
| Placebo | 19 × 7 = 133 | ≈ 14 giờ |

## Kết quả ghi ra

`results/walkforward/<cấu hình>/runs.csv` (mỗi cửa sổ × seed một dòng, có tham số template của top-5) và `returns.csv` (lợi suất ngày ngoài mẫu). Web thêm trang walk-forward khi có `runs.csv`.

## Ngoài phạm vi

SPA / DSR (Tháng 4), khung phút, kiểm tra rò rỉ qua trọng số LLM (nợ ở [PLAN](../PLAN.md#nợ)).
