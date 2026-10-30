# Kết quả hiện hành

Con số luận văn đang dùng, viết như hôm nay. Các lần chạy cũ và cách ra được số ở [log/](log/). Phương pháp ở `design/`.

## Bài cài tín hiệu

Phương pháp: [design/PLANTED_SIGNAL](design/PLANTED_SIGNAL.md). Tệp: `results/planted_window1/` (`runs.csv`, `oracle.csv`, `summary.csv`, `positions_vs_a.json`).

**Thiết lập (cách chia cửa sổ 1 walk-forward):** học 2018-08-13 → 2021-06-30 (3.583 bar 60m), kiểm định 2021-07 → 2022-06, đánh giá 2022-07 → 2022-12; ngữ pháp có lan chiều; bộ blueprint `results/blueprint_sets/20261029_212813/`; reward `sharpe`; 20 blueprint × 5.000 vòng mỗi lượt.

**A:** `ts_zscore(ts_zscore(high − close, 10) − ts_zscore(close − close, 10), 10)`, NORMALIZED, từ blueprint OrderFlowSkewnessSignal; số hạng thứ hai là hằng nên A thực chất là z-score của `ts_zscore(high − close, 10)`. 1/20 blueprint biểu diễn được A.

| IC mục tiêu | Số seed | IC đo đoạn tìm | IC đo đoạn đánh giá | Tìm lại gần | Tìm lại đúng | Sharpe ngoài mẫu (6 tháng) |
|---|---|---|---|---|---|---|
| 0 | 5 | −0.003 | −0.025 | 0/5 | 0/5 | −0.90 ± 0.46 |
| 0.05 | 5 | 0.048 | 0.021 | 1/5 | 0/5 | −0.67 ± 1.52 |
| 0.1 | 10 | 0.099 | 0.081 | **6/10** | 1/10 | −0.10 ± 1.82 |

- **Ngưỡng phát hiện ≈ IC 0.1** với lượng dữ liệu này; IC 0 không tìm nhầm lần nào.
- Tương quan của công thức gần A nhất trong top-5 ở 6 lượt tìm lại gần (IC 0.1, seed 5–10): 1.00 / 0.97 / 0.97 / 0.74 / 0.97 / 0.77. Mốc 0.8 thay cho 0.7 ⇒ 4/10. Phần lớn là cùng tín hiệu `high − close` cộng hai cửa sổ 5 và 10; "tìm lại đúng" thấp vì MCTS điền một số hạng có nghĩa vào chỗ số hạng chết của A.
- **Vị thế** (tương quan vị thế tốt nhất trong top-5 với vị thế của A trên đoạn tìm): IC 0 từ −0.09 đến 0.13 (trung bình 0.03); 6 lượt tìm lại gần ở IC 0.1: 0.72 / 0.25 / 0.66 / 0.04 / 0.46 / 0.52. Lấy mức nhiễu lớn nhất 0.13 làm mốc (đặt sau khi xem số, chỉ để tham khảo) ⇒ 0/5 / 2/5 / 6/10. Vị thế giống ít hơn giá trị thô vì ngưỡng z khác nhau: A ở ngưỡng z tốt nhất đứng ngoài 87–98% số bar.
- Sharpe ngoài mẫu 6 tháng rất nhiễu: có lượt tìm lại gần mà vẫn −2.3.

**Độ nhạy theo độ dài đoạn học** (ngữ pháp cũ, A khác: `ts_zscore(ts_max(close, 10) − ts_mean(close, 10), 10)`, `sharpe`, 5 seed; chỉ để so xu hướng):

| Đoạn học | Bar | IC 0 | IC 0.05 | IC 0.1 |
|---|---|---|---|---|
| 2018-08 → 2019-12 | 1.738 | 2/5 | 1/5 | 3/5 |
| 2018-08 → 2022-06 | 4.831 | 0/5 | 1/5 | 5/5 |

## Bộ blueprint

`results/blueprint_sets/20261029_212813/`: prompt `anon_shapes`, temperature 0.3, `qwen3.5:4b`; 20/20 đạt cả bốn tiêu chí ngay lần sinh đầu (0 chép ví dụ, 0 trùng khung, mọi blueprint có `?` và điền được ở độ sâu 4); 24 vòng hỏi, 37 phút. Gốc: 12 `greater_than`, 7 `mult`, 1 `sub`; 17/20 có `ts_zscore` hoặc `ts_rank` (gợi ý `ts_zscore(?)` trong luật chiều làm mô hình nghiêng về dạng này). `blueprints_sha256` `9b226af1…687e`, `prompt_sha256` `83c2e32f…5719` (đủ trong `generation.json`).

## Tốc độ

Một lượt chấm MCTS trên đoạn học cửa sổ 1: 19,7 ms (máy không tải). Một lượt bài cài tín hiệu cửa sổ 1 (20 blueprint × 5.000 vòng, 5 lượt song song): 1.236–1.283 s.

## Dữ liệu

- CAGR mua-và-giữ 2020–2024: 8.94% (1m), 8.93% (15m), 8.90% (60m).
- Khung phút thiếu 126 ngày giao dịch so với tệp 1H (2023-03-22 → 2024-03-14).
- Số bar walk-forward: học 3.583 (cửa sổ 1) → 7.319 (cửa sổ 7); kiểm định 1.239–1.249; đánh giá 595–650.
