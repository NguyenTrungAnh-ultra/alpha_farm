# Kết quả hiện hành

Con số luận văn đang dùng, viết như hôm nay. Các lần chạy cũ và cách ra được số ở [log/](log/). Phương pháp ở `design/`.

## Bài cài tín hiệu RQ1 (hệ thống có phản hồi, bộ RQ1)

Phương pháp: [design/LLM_FEEDBACK](design/LLM_FEEDBACK.md#bài-cài-tín-hiệu-cho-rq1). Tệp: `results/planted_rq1/` (`runs.csv`, `checkpoints.csv`, `summary.csv`, `primary_tests.csv`, `detection_thresholds.csv`, `first_touch.csv`); lệnh `main.py rq1 summary`. 3 cấu hình × A1–A4 × IC 0 / 0.05 / 0.1 × 10 seed = 360 ô, 100.000 vòng mỗi ô. Ô LLM + MCTS chạy 2026-11-01 22:00 → 2026-11-02 12:35 sau khi sửa vòng phản hồi (`6719dc9`); 90 ô hỏng trước đó lưu ở `results/planted_rq1/broken_llm_20261101/`.

**Vòng phản hồi (90 ô LLM + MCTS):** 3/90 rơi về bộ ban đầu (`context_length` 2, `all_rejected` 1); 37/90 cần thử lại, tổng 54 lần bị cắt.

**Kiểm định chính** (LLM + MCTS so với MCTS không LLM, IC 0.1, gộp theo loại A, Fisher hai phía, Holm trên 4 phép): không phép nào có ý nghĩa.

| Ngân sách | Loại A | LLM + MCTS | MCTS không LLM | p | p Holm |
|---|---|---|---|---|---|
| 50.000 | cổ điển (A1 + A2) | 6/20 | 2/20 | 0.235 | 0.940 |
| 50.000 | lạ (A3 + A4) | 2/20 | 0/20 | 0.487 | 0.974 |
| 100.000 | cổ điển | 7/20 | 3/20 | 0.273 | 0.940 |
| 100.000 | lạ | 0/20 | 1/20 | 1.000 | 1.000 |

**Tìm lại gần ở 100.000 vòng** (|Spearman| ≥ 0.7 trong top-5; mỗi ô /10; tìm ngẫu nhiên chỉ để tham khảo, ngoài kiểm định chính):

| A | IC | LLM + MCTS | MCTS không LLM | Ngẫu nhiên |
|---|---|---|---|---|
| A1 | 0 / 0.05 / 0.1 | 0 / 1 / 2 | 0 / 0 / 2 | 0 / 0 / 4 |
| A2 | 0 / 0.05 / 0.1 | 0 / 1 / **5** | 0 / 0 / 1 | 0 / 1 / 0 |
| A3 | 0 / 0.05 / 0.1 | 0 / 1 / 0 | 0 / 0 / 1 | 0 / 0 / 3 |
| A4 | 0 / 0.05 / 0.1 | 0 / 0 / 0 | 0 / 1 / 0 | 0 / 0 / 1 |

- **Ngưỡng phát hiện của LLM + MCTS (RQ2):** chỉ A2 có ngưỡng, IC 0.1 (5/10 so với 0/10 ở IC 0, p = 0.016); A1, A3, A4 không có ngưỡng trong các mức đã chạy.
- IC 0 không tìm nhầm lần nào ở cả ba cấu hình.
- A4 là A duy nhất nằm trong vùng của bộ blueprint ban đầu, nhưng LLM + MCTS tìm lại gần 0/10 ở IC 0.1.

## Bài cài tín hiệu (hệ thống sinh một lần, bộ blueprint cũ)

Phương pháp: [design/PLANTED_SIGNAL](design/PLANTED_SIGNAL.md). Tệp: `results/planted_window1/` (`runs.csv`, `oracle.csv`, `summary.csv`, `positions_vs_a.json`).

**Thiết lập (cách chia cửa sổ 1 walk-forward):** học 2018-08-13 → 2021-06-30 (3.583 bar 60m), kiểm định 2021-07 → 2022-06, đánh giá 2022-07 → 2022-12; ngữ pháp có lan chiều; bộ blueprint `results/blueprint_sets/20261029_212813/`; reward `sharpe`; 20 blueprint × 5.000 vòng mỗi lượt.

**A:** `ts_zscore(ts_zscore(high − close, 10) − ts_zscore(close − close, 10), 10)`, NORMALIZED, từ blueprint OrderFlowSkewnessSignal; số hạng thứ hai là hằng nên A thực chất là z-score của `ts_zscore(high − close, 10)`. 1/20 blueprint biểu diễn được A.

| IC mục tiêu | Số seed | IC đo đoạn tìm | IC đo đoạn đánh giá | Tìm lại gần | Tìm lại đúng | p so với IC 0 (Fisher một phía) | Sharpe ngoài mẫu (6 tháng) |
|---|---|---|---|---|---|---|---|
| 0 | 10 | −0.002 | −0.011 | 0/10 | 0/10 | — | −0.85 ± 1.00 |
| 0.05 | 10 | 0.049 | 0.035 | 2/10 | 0/10 | 0.24 | −0.45 ± 1.69 |
| 0.1 | 10 | 0.099 | 0.081 | **6/10** | 1/10 | **0.005** | −0.10 ± 1.82 |

- **Ngưỡng phát hiện: IC 0.1** (6/10 so với 0/10 ở IC 0, p = 0.005); IC 0.05 chưa tách khỏi nhiễu (2/10, p = 0.24); IC 0 không tìm nhầm lần nào.
- Tương quan của công thức gần A nhất trong top-5 ở 6 lượt tìm lại gần (IC 0.1, seed 5–10): 1.00 / 0.97 / 0.97 / 0.74 / 0.97 / 0.77. Mốc 0.8 thay cho 0.7 ⇒ 4/10. Phần lớn là cùng tín hiệu `high − close` cộng hai cửa sổ 5 và 10; "tìm lại đúng" thấp vì MCTS điền một số hạng có nghĩa vào chỗ số hạng chết của A.
- **Vị thế** (10 seed mỗi mức; tương quan vị thế tốt nhất trong top-5 với vị thế của A trên đoạn tìm): IC 0 từ −0.09 đến 0.13 (trung bình 0.04); IC 0.05 trung bình 0.16; IC 0.1 trung bình 0.30, ở 6 lượt tìm lại gần: 0.72 / 0.25 / 0.66 / 0.04 / 0.46 / 0.52. Lấy mức nhiễu lớn nhất 0.13 làm mốc (đặt sau khi xem 5 seed đầu, chỉ để tham khảo) ⇒ 0/10 / 4/10 / 6/10. Vị thế giống ít hơn giá trị thô vì ngưỡng z khác nhau: A ở ngưỡng z tốt nhất đứng ngoài 87–98% số bar.
- Sharpe ngoài mẫu 6 tháng rất nhiễu: có lượt tìm lại gần mà vẫn −2.3.

**Độ nhạy theo độ dài đoạn học** (ngữ pháp cũ, A khác: `ts_zscore(ts_max(close, 10) − ts_mean(close, 10), 10)`, `sharpe`, 5 seed; chỉ để so xu hướng):

| Đoạn học | Bar | IC 0 | IC 0.05 | IC 0.1 |
|---|---|---|---|---|
| 2018-08 → 2019-12 | 1.738 | 2/5 | 1/5 | 3/5 |
| 2018-08 → 2022-06 | 4.831 | 0/5 | 1/5 | 5/5 |

## Walk-forward thật (đóng băng `bfe7faf`)

Phương pháp: [design/WALK_FORWARD](design/WALK_FORWARD.md). Tệp: `results/walkforward/<cấu hình>/` (`runs.csv`, `returns.csv`, `summary.csv`), `results/walkforward/comparison.csv`; log `results/logs/real_llm_mcts.log`, `results/logs/real_other.log`. 7 cửa sổ, Sharpe năm trên 877 ngày ngoài mẫu (2022-07 → 2025-12), seed MCTS 1–5.

- **LLM + MCTS** (2026-11-02 18:26 → 22:03, 35 lượt, 6 worker): Sharpe seed 1 = **0.68**, p placebo = **0.15** (2/19 bộ placebo ≥ 0.68: 1.04, 0.74) ⇒ không có ý nghĩa ở 0.05. Theo seed: 0.68 / 0.21 / 0.22 / 0.47 / 0.26; chuỗi trung bình 5 seed 0.44 (mô tả).
- Năm cấu hình còn lại chạy tuần tự 18:26 → 22:12 (4 worker). Placebo chỉ có cho LLM + MCTS; `summary` in p = 1.0 cho cấu hình không có placebo, con số đó không mang nghĩa.

| Cấu hình | Sharpe theo seed (1–5) | Chuỗi trung bình | LLM + MCTS trừ cấu hình, CI 95 % | ρ | Lệnh / cửa sổ (trung vị) |
|---|---|---|---|---|---|
| LLM + MCTS | 0.68 / 0.21 / 0.22 / 0.47 / 0.26 | 0.44 | — | — | 509 |
| MCTS không LLM | 0.12 / 0.70 / −0.40 / 0.99 / 0.18 | 0.40 | +0.04 [−0.58, 0.67] | 0.81 | 298 |
| Tìm ngẫu nhiên | 0.67 / 0.77 / 0.95 / −0.67 / −0.11 | 0.46 | −0.02 [−0.64, 0.59] | 0.79 | 444 |
| LLM không tìm | 1.10 (tất định) | 1.10 | −0.66 [−1.59, 0.27] | 0.65 | 519 |
| Mua và giữ | 0.67 | 0.67 | −0.23 [−1.57, 1.03] | 0.07 | 1 |
| TSMOM | 0.08 | 0.08 | +0.37 [−1.05, 1.75] | −0.07 | 44 |

- Mọi CI chứa 0 ⇒ không phân biệt được LLM + MCTS với cấu hình nào. LLM không tìm có Sharpe cao nhất nhưng là một lần chọn duy nhất, không có placebo; hai cửa sổ 1 (2.41) và 7 (3.98) gánh phần lớn.
- Sharpe trung bình theo cửa sổ (1 → 7): LLM + MCTS 1.01 / −0.17 / −0.02 / −0.07 / 0.79 / −1.03 / 1.05; MCTS không LLM 0.73 / −1.12 / 0.05 / −0.12 / 1.05 / −1.24 / 1.20; tìm ngẫu nhiên 1.15 / −0.01 / 0.15 / −0.06 / −0.54 / −0.73 / 0.39; mua và giữ −1.43 / 1.02 / 0.04 / 1.30 / 0.68 / 0.84 / 2.45.
- Số lệnh lần thật LLM + MCTS 509, placebo 48 (chưa giải thích).
- Vòng phản hồi lần thật: 2/35 rơi về (`context_length`), 17/35 cần thử lại. Lỗi chấm 10.6 % (MCTS không LLM 8.2 %).

## Placebo walk-forward (hệ thống có phản hồi, bộ RQ1)

Phương pháp: [design/WALK_FORWARD](design/WALK_FORWARD.md#placebo). Tệp: `results/walkforward/llm_mcts/` (`runs.csv` 133 dòng, `returns.csv`, `summary.csv`), log `results/logs/placebo_llm_mcts_rerun.log`. Chạy 2026-11-01 21:56 → 2026-11-02 14:11 sau khi sửa vòng phản hồi (`6719dc9`); bản hỏng trước đó ở `results/walkforward/llm_mcts_broken_20261101/`.

**Thiết lập:** K = 19 bộ × 7 cửa sổ, MCTS seed 1, bộ blueprint `results/blueprint_sets/20261031_rq1/`, 20 blueprint × 2.500 vòng + một vòng phản hồi + 10 blueprint mới chia 50.000 vòng, reward `sharpe`; Sharpe năm trên 877 ngày ngoài mẫu (2022-07 → 2025-12).

- Sharpe 19 bộ placebo: trung bình −0.15, độ lệch chuẩn 0.58, trung vị −0.38, từ −0.94 đến **1.04**; 7/19 dương. Trung bình không khác 0 (t ≈ −1.15).
- **Mốc cho lần chạy thật:** p = 0.05 cần Sharpe thật > 1.04; > 0.74 (bộ thứ 2) cho p = 0.10.
- Vòng phản hồi: 8/133 lượt rơi về bộ ban đầu (cả 8 do `context_length` sau 3 lần thử); 63/133 cần thử lại, tổng 89 lần bị cắt.
- Lỗi chấm 10.6 %, 0 blueprint lỗi, 0 Sharpe NaN ⇒ K = 19 đủ.
- Số lệnh mỗi cửa sổ 6 tháng: trung vị 48 (0–399), hệ thống sinh một lần 343.
- Sharpe từng cửa sổ: độ lệch chuẩn 1.16–1.92 trong mỗi cửa sổ.
- Thời gian: trung bình 2.612 s mỗi lượt; 16 giờ 15 phút với 6 lượt song song, chung hàng đợi Ollama với 90 ô RQ1 tới 12:35.

## Placebo walk-forward (hệ thống sinh một lần, bộ blueprint cũ)

Phương pháp: [design/WALK_FORWARD](design/WALK_FORWARD.md#placebo). Tệp: `results/walkforward/oneshot_placebo/` (`runs.csv` 133 dòng, `returns.csv`, `summary.csv`, dòng `mode = placebo`), log `results/walkforward/placebo.log`.

**Thiết lập:** K = 19 bộ × 7 cửa sổ, MCTS seed 1, 20 blueprint × 5.000 vòng, reward `sharpe`; Sharpe năm trên chuỗi lợi suất ngày ngoài mẫu nối 7 cửa sổ (877 ngày, 2022-07 → 2025-12).

- Sharpe 19 bộ placebo: trung bình 0.11, độ lệch chuẩn 0.51, trung vị 0.07, từ −0.93 đến **1.02**; 11/19 dương.
- Trung bình không khác 0 (t ≈ 0.97); độ lệch chuẩn khớp sai số chuẩn lý thuyết của Sharpe trên 3,5 năm (≈ 1/√3,5 ≈ 0.53) ⇒ đường ống không tự sinh lợi nhuận trên dữ liệu không có tín hiệu.
- **Mốc cho lần chạy thật:** p = 0.05 cần Sharpe thật > 1.02 (lớn hơn cả 19 bộ); Sharpe 0.48 (bộ thứ 5 từ trên xuống) cho p = 0.30.
- Sharpe từng cửa sổ 6 tháng rất nhiễu: độ lệch chuẩn 0.93–1.63 trong mỗi cửa sổ.
- Lỗi chấm 6.93% (biểu thức toàn hằng), 0 blueprint lỗi, 0 Sharpe NaN ⇒ K = 19 đủ.
- Số lệnh mỗi cửa sổ 6 tháng: trung vị 343 (26–568).
- Thời gian: 133 lượt × trung bình 1.612 s; 21:02 → 03:12 (6 giờ 10 phút, 10 lượt song song).

## Rò rỉ qua trọng số LLM

`qwen3.5:4b` (Ollama, temperature 0, tắt suy nghĩ), hỏi 2026-10-31; so với giá đóng cửa cuối tháng của `data/DNSE_VN30F_1H.csv` (hợp đồng tương lai, lệch chỉ số vài điểm).

- **Ngày cắt dữ liệu:** model card Hugging Face không ghi; mô hình phát hành 2026-02 ⇒ dữ liệu huấn luyện có thể phủ cả 2020–2025. Tự khai "2026-01" khi hỏi thẳng, nhưng khi hỏi giá tháng 10/2025 lại trả lời "chúng ta đang ở 2024" ⇒ tự khai không đáng tin.
- **Mức VN30 cuối tháng, 72 tháng 2020–2025:** mô hình đoán gần như hằng (12 giá trị khác nhau cho 60 tháng 2020–2024; 1085.67 lặp 27 lần); từ 2025-04 từ chối hoặc lặp lại năm. Sai số tương đối trung bình 0.197 (64 câu có số), **tệ hơn đoán một hằng số bằng trung bình thật (0.183)**; tương quan với giá thật 0.37 (2020–2024), chỉ do mức đoán nhích theo năm.
- **Hướng tháng (tăng / giảm so với tháng trước):** đúng 48.6%, thấp hơn luôn đoán lớp đa số (58.3%); trả lời "giảm" 82% số câu.
- ⇒ Mô hình không mang thông tin dùng được về đường giá VN30 2020–2025 ở mức tháng. Không loại được rò rỉ tinh vi hơn (kiểu công thức hiệu quả), nhưng blueprint sinh với prompt ẩn tên thị trường và không thấy dữ liệu. Script: không giữ trong repo (chạy một lần).

## Bộ blueprint

`results/blueprint_sets/20261029_212813/`: prompt `anon_shapes`, temperature 0.3, `qwen3.5:4b`; 20/20 đạt cả bốn tiêu chí ngay lần sinh đầu (0 chép ví dụ, 0 trùng khung, mọi blueprint có `?` và điền được ở độ sâu 4); 24 vòng hỏi, 37 phút. Gốc: 12 `greater_than`, 7 `mult`, 1 `sub`; 17/20 có `ts_zscore` hoặc `ts_rank` (gợi ý `ts_zscore(?)` trong luật chiều làm mô hình nghiêng về dạng này). Toán tử dùng: 10/19 toán tử đã cài (`ts_zscore` 16/20 blueprint, `mult` 14, `ts_mean` 13, `greater_than` 12, `sub` 11, `ts_rank` 9, `ts_max` 8, `ts_min` 4, `ts_argmax` 1, `ts_sum` 1); không blueprint nào dùng `ts_corr`, `ts_argmin`, `add`, `div`, `less_than`, `equal`, `and_`, `or_`, `not_`. `blueprints_sha256` `9b226af1…687e`, `prompt_sha256` `83c2e32f…5719` (đủ trong `generation.json`).

**Bộ RQ1** `results/blueprint_sets/20261031_rq1/` (2026-10-31): prompt `anon_shapes` sau khi bỏ ví dụ `ts_zscore(?)`, `qwen3.5:4b` bật suy nghĩ, hỏi theo lô 10, temperature 0.3, seed 2026; 20/20 đạt tiêu chí bộ thật lần đầu (0 chép ví dụ, 0 trùng khung, 20 khung khác nhau), 4 yêu cầu, 511 s. Dùng 16/19 toán tử (bộ cũ 10/19); `ts_zscore` ở 2/20 blueprint (bộ cũ 16/20); còn thiếu `ts_argmin`, `div`, `and_`. Tổng cách điền ≈ 2.2 × 10¹⁴; 2/20 dưới 2 × 10⁴. `blueprints_sha256` `31e8c4c1…7d7d`, `prompt_sha256` `2cb84c5f…8548`.

**A trong vùng bộ RQ1:** A1, A2, A3 nằm ngoài vùng (không blueprint nào điền ra được); A4 nằm trong vùng qua `ts_argmax(?)` (≈ 1.0 × 10⁷ cách điền).

## Không gian tìm kiếm

Đếm bằng `strategy_workflows/GrammarSize.py`: số công thức hợp lệ về chiều ở 60m (4 cửa sổ mỗi toán tử `ts_*` = `scaled_periods` {2, 3, 5, 10}; 4 trường giá + khối lượng; 7 hằng ngoài toán tử cuộn; chưa nhân tham số template), `MCTS_MAX_DEPTH = 4`, gốc số nằm dưới nút template nên còn 3 tầng toán tử, gốc BOOLEAN có đủ 4 tầng:

- Cả ngữ pháp từ một ô `?`: ≈ 1.9 × 10⁴¹ (độ sâu 3: 3.1 × 10²⁰; độ sâu 2: 1.2 × 10¹⁰). Gốc BOOLEAN chiếm gần hết (cây `and_` / `or_` của các phép so lá, không có cửa sổ).
- 20 blueprint `20261029_212813` cộng lại: ≈ 1.4 × 10¹⁴ (≈ 10⁻²⁷ cả ngữ pháp). Từng blueprint: 256 → 1.0 × 10¹⁴; 8/20 dưới 2 × 10⁴, 13/20 dưới 10⁸.
- Blueprint chứa A của bài cài tín hiệu cửa sổ 1 (OrderFlowSkewnessSignal, `sub(ts_zscore(sub(pv_high, ?)), ts_zscore(sub(pv_close, ?)))`) chỉ có 256 cách điền (trước tham số template) với 5.000 vòng MCTS ⇒ gần như duyệt hết; ngưỡng phát hiện IC 0.1 vì thế đo khả năng **xếp hạng** công thức đúng lên top-5 (đoạn học → kiểm định) nhiều hơn khả năng **tìm** ra nó.

## Độ đông của công thức cài (RQ1)

Đoạn tìm cửa sổ 1 (2018-08-13 → 2022-06-30, 60m), mẫu 10.000 công thức ngẫu nhiên (ramped half-and-half, seed 2026): tỉ lệ công thức hợp lệ có \|Spearman\| ≥ 0.7 với công thức, tức xác suất "tìm lại gần" do tình cờ. Mọi công thức dưới đây qua ADF (p < 10⁻¹⁶).

| Công thức | Toán tử | Độ đông |
|---|---|---|
| `ts_zscore(close)` | 1 | 6.87% |
| `ts_rank(close)` | 1 | 6.21% |
| `sub(close, ts_mean(close))` | 2 | 5.38% |
| `ts_argmax(high)` | 1 | 2.76% |
| `ts_zscore(close − open)` | 2 | 1.67% |
| `ts_zscore(volume)` | 1 | 1.55% |
| `ts_mean(close − open)` (A2) | 2 | 0.47% |
| `ts_zscore(high − low)` | 2 | 0.28% |
| `ts_corr(close, volume)` (A1) | 1 | 0.21% |

Cửa sổ 10 cho mọi công thức. Hồi quy về trung bình trên mức giá nằm ở vùng đông: ≈ 1/15 công thức ngẫu nhiên trông giống nó.

## Tốc độ

Một lượt chấm MCTS trên đoạn học cửa sổ 1 (3 blueprint × 400 vòng, 1.196 lượt chấm): 9,8 ms. Thời gian: backtest ≈ 48%, `compute_metrics` ≈ 14%, IC xếp hạng ≈ 10%, tính công thức ≈ 13%. Kết quả giống hệt bản trước khi tăng tốc (200 backtest, 200 IC, bảng xếp hạng MCTS có seed). Một lượt bài cài tín hiệu cửa sổ 1 (20 blueprint × 5.000 vòng, 5 lượt song song): 1.236–1.283 s.

**LLM sinh blueprint** (`qwen3.5:4b`, prompt `anon_shapes` 60m ≈ 1.720 token vào, 2026-10-31, một yêu cầu): bật suy nghĩ (mặc định của `OllamaChatClient`, không truyền `think`) 90,9 s, 8.843 token ra; tắt suy nghĩ 3,3–7,3 s, 121 token ra. Bộ `20261029_212813` sinh khi bật suy nghĩ: 24 yêu cầu, 2.241 s. Một yêu cầu bật suy nghĩ xin 10 blueprint cùng lúc (lô thử, không chấm dữ liệu): 99,9 s, 9.348 token ra, 10/10 biên dịch được, 10 khung khác nhau.

**Một lượt RQ1 đủ cỡ** (cửa sổ 1, 100.000 vòng, 2026-10-31, 5 lượt LLM + MCTS chạy cùng lúc với 2 lượt cấu hình khác; thư mục thử `results/planted_rq1_timing/`, không dùng làm kết quả): MCTS không LLM 446–449 s (65–75 nghìn lượt chấm); tìm ngẫu nhiên 261–262 s (60.725 công thức khác nhau trên 100.000 mẫu, 39% trùng, chủ yếu ở độ sâu 1); LLM + MCTS 631–1.398 s, trong đó phần không phải LLM ≈ 520–630 s và LLM 109 s khi chạy một mình, tới 811 s khi xếp hàng sau các lượt khác (Ollama xử lý từng yêu cầu một); 1–2 yêu cầu mỗi lượt.

## Dữ liệu

- CAGR mua-và-giữ 2020–2024: 8.94% (1m), 8.93% (15m), 8.90% (60m).
- Khung phút thiếu 126 ngày giao dịch so với tệp 1H (2023-03-22 → 2024-03-14).
- Số bar walk-forward: học 3.583 (cửa sổ 1) → 7.319 (cửa sổ 7); kiểm định 1.239–1.249; đánh giá 595–650.
