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

1. Tìm trên đoạn học, reward `sharpe`, 100.000 vòng MCTS. Hệ thống chính (`--system llm_mcts`): 20 blueprint `results/blueprint_sets/20261031_rq1/` × 2.500 vòng, một vòng phản hồi LLM, 10 blueprint mới × 5.000 vòng, chạy luân phiên từng đoạn 500 vòng ([LLM_FEEDBACK](LLM_FEEDBACK.md#hệ-thống-llm--mcts-có-phản-hồi)). Bản sinh một lần cũ (`--system oneshot`, 20 × 5.000 tuần tự) giữ để chạy lại placebo 2026-10-31.
2. ≤ 100 biểu thức khác nhau tốt nhất → chấm lại trên đoạn kiểm định → top-5.
3. Vị thế top-5 trọng số đều, giao dịch trên đoạn đánh giá (phí, ký quỹ như `AlphaBacktestEngine`); lịch sử chỉ báo lấy từ khung liên tục.
4. Ghi lợi suất ngày của đoạn đánh giá, top-5 (biểu thức + tham số template + chiều), reward học / kiểm định.
5. 5 seed (1–5) mỗi cấu hình tìm; LLM không tìm, mua và giữ, TSMOM chỉ seed 1 (tất định).

Lợi suất ngày = chênh lệch vốn cuối ngày chia vốn ban đầu; Sharpe = trung bình / độ lệch (ddof 0) × √252.

## Cấu hình so sánh

Cùng ngân sách 100.000 lượt chấm mỗi cửa sổ, cùng bước 2–4. Hệ thống chính có vòng phản hồi LLM và cách làm từng cấu hình: [LLM_FEEDBACK](LLM_FEEDBACK.md#các-cấu-hình). Cả sáu cấu hình đã có code (chưa chạy); `--system` chọn cấu hình, mô tả ở [ARCH](ARCH.md) mục 3.5–3.8.

| Cấu hình | Cách làm | RQ | Code |
|---|---|---|---|
| LLM + MCTS | như mục trên | 1, 2 | ✅ |
| MCTS không có LLM | MCTS từ một ô `?` dưới mỗi template NORMALIZED / BOOLEAN / RATIO, chia đều 100.000 vòng | 1 | ✅ |
| LLM không tìm | LLM viết một lần 100 công thức hoàn chỉnh (không `?`, 10 yêu cầu × 10, đóng băng); mỗi cửa sổ chấm hết trên lưới tham số khuôn của MCTS (ngoại lệ ngân sách: ≈ 2.500 lượt chấm, không phải 100.000); chỉ seed 1 vì LLM không thấy dữ liệu | 1 | ✅ |
| Tìm ngẫu nhiên | 100.000 công thức hợp lệ về chiều, sinh theo kích thước (ramped half-and-half) | 1 | ✅ |
| Mua và giữ | luôn long, cùng cỡ vị thế, phí và ký quỹ; chỉ seed 1 | tham chiếu | ✅ |
| TSMOM | momentum chuỗi thời gian (Moskowitz 2012) trên bar 60m: dấu lợi suất L bar, không chia theo biến động; L ∈ {1 phiên, 1 tuần, 1 tháng} chọn theo Sharpe kiểm định; chỉ seed 1 | tham chiếu | ✅ |

**Độ chênh Sharpe phát hiện được** (877 ngày; Memmel 2003, một phía α = 0.05): phương sai của chênh lệch Sharpe ngày = (2 − 2ρ + ½(sr₁² + sr₂² − 2ρ²sr₁sr₂)) / 877, sr là Sharpe theo ngày, ρ là tương quan lợi suất ngày giữa hai cấu hình (chưa đo, chờ lần chạy thật); nhân √252 ra theo năm. Số hạng sr² nhỏ không đáng kể với dữ liệu ngày (Sharpe năm 1 ⇒ sr² ≈ 0.004). Chênh tối thiểu với power 50% / 80%: ρ = 0 ⇒ 1.25 / 1.89; ρ = 0.3 ⇒ 1.04 / 1.58; ρ = 0.5 ⇒ 0.88 / 1.33; ρ = 0.7 ⇒ 0.68 / 1.03. Một Sharpe đơn lẻ có sai số chuẩn 0.54 (placebo đo được 0.51).

## Placebo

- Lặp toàn bộ walk-forward của LLM + MCTS trên K = 19 bộ placebo: hoán vị lợi suất trong từng đoạn (học, kiểm định, đánh giá xáo riêng), mỗi cửa sổ một bản hoán vị riêng, seed = 100000 + 100·k + w.
- Một seed MCTS (seed 1) mỗi bộ. Bộ placebo có Sharpe NaN không tính vào K.
- p = (1 + số bộ placebo có Sharpe ≥ lần thật) / (K + 1); nhỏ nhất 0.05. "Lần thật" ở đây là chuỗi lợi suất thật của riêng MCTS seed 1 (cùng seed, cùng cách đo với bộ placebo; dòng `real_seed1` của `summary.csv`). Trung bình ngày của 5 seed (dòng `real_mean`) vẫn được báo cáo nhưng chỉ để mô tả, không có p, vì trung bình nhiều seed làm chuỗi mượt hơn (vol thấp, |Sharpe| cao hơn khi trung bình khác 0) nên thiên về lần thật so với placebo một seed. Thiếu seed 1 ở lần thật thì p để trống. So sánh giữa các cấu hình (`comparison.csv`) vẫn dùng trung bình 5 seed.

## Đóng băng

`main.py walkforward freeze --formulas <formulas.json>` ghi `results/walkforward/frozen.json`: reward + `REWARD_WEIGHTS`, bảng cửa sổ, tệp blueprint (sha256), bộ công thức của LLM không tìm (đường dẫn, sha256, sha256 bản ghi sinh) và lưới tham số khuôn của nó, lưới TSMOM (số phiên, luật chọn), cỡ vị thế tham chiếu, ngân sách, mô hình LLM, seed từng cấu hình, khung, `MAX_RANKED`, `TOP_K`, commit git, dấu vân tay dữ liệu. `real` từ chối chạy nếu bất kỳ trường nào khác bản đóng băng, hoặc `git diff --name-only <commit đóng băng>` trên `main.py`, `core_engine/`, `strategy_workflows/`, `utilities/` không rỗng. Vì thế mọi code (kể cả cấu hình so sánh) phải xong trước khi đóng băng.

## Bộ blueprint

Bộ đóng băng: `results/blueprint_sets/20261031_rq1/` (cùng bộ với placebo và bài cài tín hiệu RQ1; `20261029_212813/` là bộ của hệ thống sinh một lần, vẫn là mặc định `DEFAULT_BLUEPRINTS` trong code nên lệnh `freeze` / `real` phải truyền `--blueprints`). Tiêu chí bộ thật: 0 blueprint trùng nguyên văn ví dụ trong prompt; không hai blueprint cùng khung (so cấu trúc cây, bỏ qua tên trường điền sẵn); mọi blueprint có ≥ 1 `?` và biên dịch được; `qwen3.5:4b`, 20 blueprint. Số liệu của bộ: [RESULTS](../RESULTS.md#bộ-blueprint).

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
