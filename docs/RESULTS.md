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

## Bộ blueprint

`results/blueprint_sets/20261029_212813/`: prompt `anon_shapes`, temperature 0.3, `qwen3.5:4b`; 20/20 đạt cả bốn tiêu chí ngay lần sinh đầu (0 chép ví dụ, 0 trùng khung, mọi blueprint có `?` và điền được ở độ sâu 4); 24 vòng hỏi, 37 phút. Gốc: 12 `greater_than`, 7 `mult`, 1 `sub`; 17/20 có `ts_zscore` hoặc `ts_rank` (gợi ý `ts_zscore(?)` trong luật chiều làm mô hình nghiêng về dạng này). `blueprints_sha256` `9b226af1…687e`, `prompt_sha256` `83c2e32f…5719` (đủ trong `generation.json`).

## Tốc độ

Một lượt chấm MCTS trên đoạn học cửa sổ 1 (3 blueprint × 400 vòng, 1.196 lượt chấm): 9,8 ms. Thời gian: backtest ≈ 48%, `compute_metrics` ≈ 14%, IC xếp hạng ≈ 10%, tính công thức ≈ 13%. Kết quả giống hệt bản trước khi tăng tốc (200 backtest, 200 IC, bảng xếp hạng MCTS có seed). Một lượt bài cài tín hiệu cửa sổ 1 (20 blueprint × 5.000 vòng, 5 lượt song song): 1.236–1.283 s.

## Dữ liệu

- CAGR mua-và-giữ 2020–2024: 8.94% (1m), 8.93% (15m), 8.90% (60m).
- Khung phút thiếu 126 ngày giao dịch so với tệp 1H (2023-03-22 → 2024-03-14).
- Số bar walk-forward: học 3.583 (cửa sổ 1) → 7.319 (cửa sổ 7); kiểm định 1.239–1.249; đánh giá 595–650.
