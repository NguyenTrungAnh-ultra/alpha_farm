# Kết quả hiện hành

Con số luận văn đang dùng, viết như hôm nay. Các lần chạy cũ và cách ra được số ở [log/](log/). Phương pháp ở `design/`.

## Bài cài tín hiệu

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

## Placebo walk-forward

Phương pháp: [design/WALK_FORWARD](design/WALK_FORWARD.md#placebo). Tệp: `results/walkforward/llm_mcts/` (`runs.csv` 133 dòng, `returns.csv`, `summary.csv`, dòng `mode = placebo`), log `results/walkforward/placebo.log`.

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

## Không gian tìm kiếm

Đếm số công thức hợp lệ về chiều (5 cửa sổ mỗi toán tử `ts_*` ở 60m, 4 trường giá + khối lượng, 7 hằng ngoài toán tử cuộn; chưa nhân tham số template: 5 ngưỡng z hoặc 5 × 5 ngưỡng RATIO), `MCTS_MAX_DEPTH = 4`, gốc số nằm dưới nút template nên còn 3 tầng toán tử, gốc BOOLEAN có đủ 4 tầng:

- Cả ngữ pháp từ một ô `?`: ≈ 1.9 × 10⁴¹ (độ sâu 3: 3.1 × 10²⁰; độ sâu 2: 1.2 × 10¹⁰).
- 20 blueprint `20261029_212813` cộng lại: ≈ 4.6 × 10¹⁴ (≈ 2.4 × 10⁻²⁷ cả ngữ pháp). Từng blueprint: 400 → 3.2 × 10¹⁴; 6/20 dưới 2 × 10⁴, 10/20 dưới 10⁸.
- Blueprint chứa A của bài cài tín hiệu cửa sổ 1, `sub(ts_zscore(sub(pv_high, ?)), ts_zscore(sub(pv_close, ?)))`, chỉ có 400 cách điền (trước tham số template) với 5.000 vòng MCTS ⇒ gần như duyệt hết; ngưỡng phát hiện IC 0.1 vì thế đo khả năng **xếp hạng** công thức đúng lên top-5 (đoạn học → kiểm định) nhiều hơn khả năng **tìm** ra nó.

## Tốc độ

Một lượt chấm MCTS trên đoạn học cửa sổ 1 (3 blueprint × 400 vòng, 1.196 lượt chấm): 9,8 ms. Thời gian: backtest ≈ 48%, `compute_metrics` ≈ 14%, IC xếp hạng ≈ 10%, tính công thức ≈ 13%. Kết quả giống hệt bản trước khi tăng tốc (200 backtest, 200 IC, bảng xếp hạng MCTS có seed). Một lượt bài cài tín hiệu cửa sổ 1 (20 blueprint × 5.000 vòng, 5 lượt song song): 1.236–1.283 s.

**LLM sinh blueprint** (`qwen3.5:4b`, prompt `anon_shapes` 60m ≈ 1.720 token vào, 2026-10-31, một yêu cầu): bật suy nghĩ (mặc định của `OllamaChatClient`, không truyền `think`) 90,9 s, 8.843 token ra; tắt suy nghĩ 3,3–7,3 s, 121 token ra. Bộ `20261029_212813` sinh khi bật suy nghĩ: 24 yêu cầu, 2.241 s.

## Dữ liệu

- CAGR mua-và-giữ 2020–2024: 8.94% (1m), 8.93% (15m), 8.90% (60m).
- Khung phút thiếu 126 ngày giao dịch so với tệp 1H (2023-03-22 → 2024-03-14).
- Số bar walk-forward: học 3.583 (cửa sổ 1) → 7.319 (cửa sổ 7); kiểm định 1.239–1.249; đánh giá 595–650.
