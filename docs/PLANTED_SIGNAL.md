# Thiết kế — Bài cài tín hiệu (việc 3, kiểm soát dương RQ2)

Bản hiện hành. Đổi ý thì sửa đúng chỗ, kèm một dòng lý do + ngày.
Nguồn: proposal mục "Planted-Signal Test"; ROADMAP mục 2 việc 3.

Trạng thái: 🔧 đang code. Người dùng duyệt toàn bộ các lựa chọn **[đề xuất]** ngày 2026-10-28.

## 1. Câu hỏi bài test trả lời

Nếu dữ liệu thật sự chứa một công thức mà ngữ pháp biểu diễn được, với độ mạnh IC biết trước, thì quy trình (MCTS trên bộ blueprint đã đóng băng) có tìm lại được không, và Sharpe ngoài mẫu đạt bao nhiêu? Không tìm lại được ở IC 0.05 ⇒ quy trình mù, phải sửa trước khi chạy walk-forward.

## 2. Dữ liệu

- **Khung và cửa sổ [đề xuất]:** 60m (tệp 1H không thiếu ngày, chạy nhanh). Dùng hình dạng cửa sổ walk-forward đầu tiên: tìm 2018-08-13 → 2020-06-30, đánh giá 2020-07-01 → 2020-12-31.
- **Nền placebo:** hoán vị lợi suất bar trong từng đoạn (tìm, đánh giá) như proposal. Mỗi bar mang theo Volume và hình dạng trong bar (Open/High/Low so với Close) của chính nó, rồi dựng lại giá từ lợi suất.
- **Cài tín hiệu [đề xuất]:** sinh tuần tự từng bar, vì công thức phụ thuộc giá mà giá lại phụ thuộc lợi suất đã cài:
  - `s_t = ts_zscore(A, W)` tính trên giá đã dựng tới bar t, với `A` là công thức cài;
  - `r_{t+1} = ε_{t+1} + β · σ_ε · s_t`, trong đó `ε` là lợi suất placebo đã hoán vị.
- **Hiệu chỉnh độ mạnh:** tìm `β ≥ 0` bằng chia đôi sao cho **IC Spearman trung bình trên 20 hoán vị hiệu chỉnh** (seed 1001–1020, khác seed của lượt chạy) trên đoạn tìm bằng IC mục tiêu. Một `β` cho mỗi độ mạnh, dùng chung cho mọi seed và cả đoạn đánh giá. IC đo được của từng seed = mục tiêu + nhiễu mẫu; báo cáo IC đo được ở cả hai đoạn. (Sửa lần 2, 2026-10-28, Claude quyết: hiệu chỉnh theo từng seed buộc `β` âm để triệt tiêu IC ngẫu nhiên của chính placebo (±0.02), tức là "tín hiệu" khi đó là nhiễu trùng hợp chứ không phải công thức cài.)
- **Ngưỡng nhiễu:** đoạn tìm ≈ 3.000 bar ⇒ sai số chuẩn của IC ≈ 1/√3000 ≈ 0.018; đoạn đánh giá ≈ 600 bar ⇒ ≈ 0.04. IC 0.01 / 0.02 nằm dưới ngưỡng nhiễu của đoạn tìm, nên tìm lại được ở hai mức này là may; chỉ IC 0.05 (≈ 2.8 sai số chuẩn) có tiêu chí. (Sửa 2026-10-28, Claude quyết: công thức `β = IC / sqrt(1 − IC²)` nhắm tương quan Pearson; lợi suất 60m đuôi dày (kurtosis ≈ 28) nên IC Spearman đo được gấp ≈ 2 lần mục tiêu — nhãn "IC 0.05" thực ra là 0.10–0.14, bài test dễ hơn thiết kế.)
- **Độ mạnh:** IC = 0 (placebo thuần, đo tỷ lệ "tìm nhầm"), 0.01, 0.02, 0.05.

## 3. Công thức cài và blueprint

- **[đề xuất]** Sinh bộ blueprint một lần bằng `ollama-local` (20 ý tưởng, khung 60m) và đóng băng vào `results/planted/blueprints.json`. Bộ này dùng lại cho walk-forward.
- Chọn công thức cài sao cho **ít nhất một** blueprint trong bộ biểu diễn được nó, nhưng không trùng nguyên văn blueprint nào. Ứng viên mặc định: `sub(close, ts_mean(close, 10))` dưới template NORMALIZED, cửa sổ z-score 10. (Sửa 2026-10-28: ở 60m các chu kỳ quy đổi từ 10m chỉ còn {2, 3, 5, 10}, nên 20 không nằm trong không gian tìm.) Ghi rõ blueprint nào chạm được công thức đó.
- Lý do: nếu không blueprint nào biểu diễn được công thức cài thì "không tìm lại" là do bộ blueprint chứ không do MCTS, bài test vô nghĩa.
- ⛔ **Bộ sinh lần 1 (2026-10-28, `results/planted/blueprints.json`, 20/20 qua biên dịch) không dùng được:** 19/20 blueprint không có ô `?` nào (LLM viết công thức trọn vẹn), nên MCTS chỉ còn chọn cửa sổ và ngưỡng. Không blueprint nào biểu diễn được công thức cài theo phép khớp cấu trúc; riêng `sub(ts_mean(pv_close), pv_close)` là −A (cùng nghĩa vì backtest thử cả hai chiều) nhưng không có ô nào. Người dùng chốt (2026-10-28): sửa prompt + loại blueprint không có `?` (áp cho cả `main.py generate`), thử 5 blueprint với 4B trước; chỉ khi hết cách mới thử `ollama-9b`; không dùng bộ viết tay.
- ✅ Thử 5 blueprint với prompt mới (2026-10-28, 4B): 5/5 có ô `?` (1–2 ô mỗi blueprint), mất ~8 vòng hỏi. Không blueprint nào biểu diễn được `sub(close, ts_mean(close, 10))` — công thức mặc định chỉ là ứng viên, đúng như mục này đã nói.
- **Luật chọn công thức cài (chốt trước khi xem bộ 20, Claude quyết 2026-10-28, theo đúng nguyên tắc ở trên):** đi theo thứ tự trong `blueprints.json`, lấy blueprint đầu tiên có ≥ 2 ô `?` và gốc thuộc template NORMALIZED. Công thức cài = blueprint đó với mọi `?` điền `pv_close` và mọi cửa sổ = 10 (cửa sổ z-score 10). Nếu kết quả trùng nguyên văn một blueprint thì lấy blueprint kế tiếp. Nếu kết quả là hằng (ví dụ `(close − close) × …`, không có tín hiệu để cài) thì cũng lấy blueprint kế tiếp. Không blueprint nào thoả ⇒ báo người dùng, không tự nới luật. (Thêm điều khoản "hằng" 2026-10-30, người dùng chốt: bộ 20 blueprint mới hay đặt `pv_close` cạnh ô `?`, nên blueprint đầu tiên thoả luật điền ra công thức bằng 0. Công thức có một số hạng chết nhưng không hằng thì vẫn giữ, vì `ts_zscore` của chuỗi hằng trả 0 nên số hạng đó không làm hỏng tín hiệu; chỉ chỉ số "tìm lại đúng" khó hơn vì MCTS phải điền đúng `close` vào ô chết.)
- ✅ **Bộ chính thức (2026-10-28, 4B, prompt mới):** 20/20 có ô `?` (1–4 ô), không bị loại lần nào. Luật chọn ra blueprint đầu tiên `sub(ts_max(?), ts_mean(?))` ⇒ công thức cài `ts_zscore(ts_max(close, 10) − ts_mean(close, 10), 10)`, NORMALIZED; 1/20 blueprint biểu diễn được. Lưu ý cho RQ1: blueprint này và `sub(ts_mean(?), ts_mean(?))` trùng nguyên văn ví dụ mẫu trong prompt — mô hình 4B có chép ví dụ.
- **Chấm đáp án trên công thức này (`oracle.csv`, 27 s):** soft trung bình 0.305 / 0.317 / 0.416 / 0.474 ở IC 0 / 0.01 / 0.02 / 0.05; gated qua cổng 2 / 2 / 3 / 4 trên 5. Tăng theo IC nhưng yếu: điểm phụ thuộc hoán vị nhiều hơn tín hiệu (seed 2 và 4 được 0.62–0.78 ở mọi độ mạnh, kể cả IC 0, Calmar ≈ 4). Suy đoán của Claude (chưa đo): Calmar trên đoạn 2 năm rất nhiễu, và công thức này nhặt được xu hướng mà hoán vị vẫn giữ (lợi suất trung bình của đoạn). Bảng tìm lại mới là thước đo chính.

## 8. Kết quả lần chạy 1 (2026-10-28, soft, 5.000 vòng × 20 blueprint, 20 lượt, mỗi lượt 1.300–1.570 s trên 10 tiến trình)

| IC | IC đo đoạn tìm | tìm lại đúng | tìm lại gần | Sharpe ngoài mẫu |
|---|---|---|---|---|
| 0 | 0.000 | 0/5 | 0/5 | −2.30 ± 0.41 |
| 0.01 | 0.015 | 0/5 | 0/5 | −0.96 ± 1.03 |
| 0.02 | 0.026 | 0/5 | 0/5 | 0.25 ± 1.46 |
| 0.05 | 0.058 | 0/5 | 1/5 | −0.13 ± 0.44 |

- ⛔ **Tiêu chí IC 0.05 trượt** (cần ≥ 3/5, được 1/5). Tiêu chí IC 0 đạt (0/5).
- Reward tốt nhất MCTS tìm được là 0.73–0.86 ở **mọi** độ mạnh, kể cả IC 0, cao hơn điểm của chính công thức cài (trung bình 0.47 ở IC 0.05). Tức là trong ~60.000 công thức chấm trên ~2.300 bar, công thức nhiễu tốt nhất luôn thắng tín hiệu thật ở IC 0.05: reward trong mẫu bị chọn-quá-khớp (đa kiểm định), không phải MCTS tìm kém.
- Sharpe ngoài mẫu ở IC 0 là −2.3: alpha nhiễu giao dịch nhiều và thua phí.
- ⛔ Lỗi phát hiện: top-5 có công thức trùng nhau (cùng biểu thức, khác tham số template), nên "gộp top-5" thực chất gộp 1–3 công thức.
- ~4–5% lượt chấm lỗi vì biểu thức hằng (`ts_mean(volume*0.05)`… và lỗi shape) — nợ đã ghi.
- ✅ Người dùng chốt làm cả ba (2026-10-28), áp cho lần chạy 2:
  - **(a)** top-5 là 5 **biểu thức khác nhau**; mỗi biểu thức giữ bộ tham số template tốt nhất.
  - **(b)** đoạn tìm tách hai: MCTS chạy trên **2018-08-13 → 2019-12-31** (đoạn học), top-5 chọn theo reward soft trên **2020-01-01 → 2020-06-30** (đoạn kiểm định), xếp hạng trong ≤ 100 ứng viên khác biểu thức của leaderboard. Alpha tính trên chuỗi liền nên cửa sổ không bị cắt. β vẫn hiệu chỉnh trên cả đoạn tìm; "tìm lại gần" vẫn đo trên cả đoạn tìm. Đây là thay đổi phương pháp, luận văn phải ghi; walk-forward sẽ dùng cùng cách tách (6 tháng cuối của 2 năm tìm).
  - **(c)** thêm độ mạnh IC 0.1 và 0.2 (chỉ báo cáo, không đặt ngưỡng) ⇒ 6 độ mạnh × 5 seed = 30 lượt.
  - Tiêu chí đạt giữ nguyên (IC 0.05: gần ≥ 3/5; IC 0: gần ≤ 1/5).

## 9. Kết quả lần chạy 2 (2026-10-28, soft, 5.000 vòng × 20 blueprint, học 2018-08→2019-12, chọn trên 2020-01→06; 30 lượt, mỗi lượt 1.580–1.710 s, tổng ≈ 85 phút trên 10 tiến trình)

| IC mục tiêu | IC đo đoạn tìm | tìm lại đúng | tìm lại gần | Sharpe ngoài mẫu |
|---|---|---|---|---|
| 0 | 0.000 | 0/5 | 0/5 | −2.17 ± 2.09 |
| 0.01 | 0.015 | 0/5 | 0/5 | −0.31 ± 2.04 |
| 0.02 | 0.026 | 0/5 | 0/5 | 0.12 ± 1.67 |
| 0.05 | 0.058 | 0/5 | 1/5 | −0.65 ± 1.52 |
| 0.1 | 0.109 | 0/5 | 3/5 | 0.74 ± 1.33 |
| 0.2 | 0.206 | 1/5 | 5/5 | 1.79 ± 1.43 |

- ⛔ **Tiêu chí IC 0.05 vẫn trượt** (1/5). Tiêu chí IC 0 đạt (0/5).
- **Ngưỡng phát hiện đo được ≈ IC 0.1** (3/5 gần), IC 0.2 tìm lại 5/5. Sharpe ngoài mẫu tăng theo IC (−2.2 ở placebo → +1.8 ở IC 0.2): quy trình có cảm được tín hiệu, nhưng chỉ khi tín hiệu mạnh gấp đôi mức thiết kế.
- Ở IC 0.05, công thức gần đáp án (|Spearman| ≥ 0.7) **có** nằm trong ≤ 100 ứng viên ở 2/5 seed (seed 3: hạng học 75 → hạng kiểm định 10; seed 4: 46 → 1). Đoạn kiểm định có kéo nó lên, nhưng 6 tháng (~600 bar) vẫn quá nhiễu để đưa lên top-5 đều đặn.
- So lần 1 (không có đoạn kiểm định, cùng IC 0.05): vẫn 1/5 ⇒ riêng đoạn kiểm định không đủ để đạt tiêu chí.
- ⏸️ Người dùng cho tạm dừng sau lần chạy này (2026-10-28); hướng tiếp theo chưa chọn.

**Đo phễu (2026-10-29, người dùng hỏi "xác suất tìm được với kiến trúc hiện tại"):** chạy lại MCTS của blueprint chứa A (`sub(ts_max(?), ts_mean(?))`, đứng đầu tệp nên cùng seed cho đúng chuỗi tìm của lần 2), ghi mọi lượt chấm; 30 lượt (6 độ mạnh × 5 seed), soft.
- Không gian: đường tới A qua 6 lựa chọn (cửa sổ 4 × ô `?` 14 × cửa sổ 4 × ô `?` 14 × cửa sổ z 5, ngưỡng z tuỳ) ⇒ một lượt rollout ngẫu nhiên đều ra đúng A với xác suất 1/15.680.
- **Tầng 1 — MCTS có chấm tới A (cửa sổ lệch ≤ 1 nấc) không:** 26/30 lượt, thường trong 1.000 vòng đầu (IC 0.05: 4/5). Bước tìm không phải chỗ nghẽn chính.
- **Tầng 2 — chấm đủ tham số template:** ở IC 0 – 0.05, A chỉ được thử trung bình 2–5 tổ hợp (cửa sổ z × ngưỡng z), thường chỉ 1–2; tổ hợp đầu điểm thấp thì UCT theo max không quay lại. Điểm A lúc tìm ở IC 0.05: trung bình 0.30, so với 0.58 khi chấm với tham số tốt nhất (oracle).
- **Tầng 3 — kể cả với tham số tốt nhất, A có thắng nhiễu không:** điểm oracle của A trên đoạn học ở IC 0.05 dao động 0.11–0.79 theo seed. Nó vượt ngưỡng 100 ứng viên của **riêng blueprint này** ở 2/5 seed, vượt ứng viên tốt nhất của blueprint ở 1/5 (IC 0.1: 3/5 và 2/5; IC 0.2: 5/5 và 2/5). Toàn bộ 20 blueprint chung một bảng 100 nên ngưỡng thật còn cao hơn.
- **A "tốt" đến đâu trên dữ liệu hữu hạn (2026-10-29, người dùng hỏi "dựa vào chỉ số nào bảo A tốt"):** A tốt theo cách dựng dữ liệu (quan hệ dự báo duy nhất có thật), không theo chỉ số nào của hệ thống. Đo trên đoạn đánh giá (6 tháng): IC của A ở mức 0.05 chỉ còn trung bình 0.03 (−0.01 … 0.10 theo seed). Sharpe ngoài mẫu của chính A (chiều +1, cửa sổ z 10, trung bình 5 ngưỡng z): 0.22 / 0.84 / 1.29 / 2.20 ở IC 0 / 0.05 / 0.1 / 0.2, độ lệch giữa seed ≈ ±1.5; top-5 của hệ thống −2.17 / −0.65 / 0.74 / 1.79. Ở IC 0.05, lợi thế của A so với placebo (≈ 0.6 Sharpe) nhỏ hơn nhiễu giữa seed.
- Ước lượng của Claude (chưa kiểm): sai số IC trên đoạn học ≈ 1/√2300 ≈ 0.021; công thức nhiễu tốt nhất trong ~80.000 lượt chấm đạt khoảng √(2 ln 80000) ≈ 4.75 sai số ≈ 0.10 (cận trên, vì các công thức tương quan với nhau). Khớp ngưỡng phát hiện đo được ≈ IC 0.1 ⇒ ở IC 0.05, nghẽn chủ yếu do lượng dữ liệu so với số công thức thử, không riêng do reward hay MCTS.
- Suy đoán của Claude (chưa đo tách riêng): chỗ nghẽn chính là reward trên ~2.300 bar không phân biệt được IC 0.05 với nhiễu (phần Calmar nặng 0.6 phụ thuộc hoán vị hơn tín hiệu); chỗ nghẽn phụ là MCTS chỉ thử A ở 1–2 bộ tham số template.

## 10. Lần chạy 3: dữ liệu gấp ≈ 2–3 lần (người dùng duyệt 2026-10-29)

Người dùng chọn hướng "thêm dữ liệu" (2026-10-29) để kiểm giả thuyết ở mục 9: ở IC 0.05, nghẽn chủ yếu do lượng dữ liệu so với số công thức thử. Người dùng chốt không dùng năm 2025 (giữ ngoài mọi bài test); trước 2018-08 không có dữ liệu.

- **Thay đổi duy nhất so với lần 2: độ dài các đoạn.** Dùng tệp 60m từ 2018-08-13 tới 2024-12-31 (7.967 bar):

  | Đoạn | Lần 2 | Lần 3 | Số bar lần 3 |
  |---|---|---|---|
  | Học | 2018-08 → 2019-12 | 2018-08 → 2022-06 | 4.831 (≈ 2,1×) |
  | Kiểm định | 2020-01 → 2020-06 | 2022-07 → 2023-12 | 1.888 (≈ 3,1×) |
  | Đánh giá | 2020-07 → 2020-12 | 2024-01 → 2024-12 | 1.248 (≈ 2,1×) |

  Giữ nguyên: công thức cài A, bộ 20 blueprint, soft, 5.000 vòng, 5 seed, top-5 khác biểu thức chọn trên đoạn kiểm định, tiêu chí tìm lại. β hiệu chỉnh lại cho độ dài mới (khoá hiệu chỉnh đã gồm khoảng dữ liệu).
- **Độ mạnh:** 0 / 0.02 / 0.05 / 0.1 (bỏ 0.01 và 0.2: dưới nhiễu và đã đạt 5/5) ⇒ 20 lượt. Ước ≈ 3 giờ trên 10 tiến trình (lần 2: ≈ 28 phút/lượt với 1/3 số bar; chưa đo).
- **Dự đoán chốt trước khi chạy (Claude, ước lượng nhẩm):** sai số IC tỷ lệ 1/√số bar ⇒ mức hên của nhiễu giỏi nhất ở đoạn học ≈ 0.09 → 0.06, ở đoạn kiểm định (100 ứng viên) ≈ 0.10 → 0.06. Ngưỡng phát hiện dự kiến tụt từ ≈ 0.1 xuống ≈ 0.06; IC 0.05 sát ngưỡng, dự kiến tìm lại gần 1–3/5.
  - Giả thuyết được ủng hộ nếu: tỷ lệ tìm lại gần ở IC 0.05 và 0.1 cao hơn lần 2 (1/5 và 3/5), IC 0 vẫn 0/5.
  - Bị bác nếu: tỷ lệ ở IC 0.05 và 0.1 không tăng ⇒ nghẽn không do dữ liệu, quay lại xét reward / MCTS.
- ✅ Code (2026-10-29): `Segments` trong `PlantedSignal.py`; `main.py planted select|oracle|search --train-end --search-end --eval-end --formula`, ghi `<out-dir>/segments.json` và từ chối trộn hai cách chia. Kết quả lần 3: `results/planted_run3/`. Test: 145 pass, 1 fail (có từ trước).
- ⏸️ **Chấm đáp án lần 3 (`results/planted_run3/oracle.csv`, 66 s) lộ một yếu tố gây nhiễu, chưa chạy `search`:**
  - β hiệu chỉnh đúng mục tiêu (IC trung bình 0.021 / 0.051 / 0.100).
  - Nhưng reward soft của chính A trên đoạn học tụt mạnh: trung bình 0.05 / 0.07 / 0.23 ở IC 0 / 0.05 / 0.1 (lần 2: 0.32 / 0.58 / 0.78). Ở IC 0.1, 4/5 seed chỉ còn 0.09–0.14.
  - Nguyên nhân đo được: không phải gọi ký quỹ (chỉ 1/20 trường hợp kiểm có đóng băng vốn). Vốn của A vẫn tăng tương đương lần 2 (IC 0.1: ×1.24–3.06 sau ~3,9 năm), nhưng sụt giảm lớn nhất (MDD) tăng theo độ dài đoạn ⇒ Calmar tụt xuống dưới ngưỡng 1.1 ⇒ phần Calmar của reward (trọng số 0.6) gần như luôn bằng 0. Reward lần 3 thực chất chỉ còn phần IC; vì phần IC không phụ thuộc ngưỡng z nên ngưỡng z chọn ra luôn là 0.5 (hoà điểm, lấy giá trị đầu).
  - Phần IC tính trên giá trị thô của công thức, không trên z-score: ở IC 0.05, IC thô của A chỉ ≈ 0.017 trong khi IC của tín hiệu đã cài ≈ 0.04 (suy đoán của Claude: giá trị thô đổi thang theo mức giá qua nhiều năm).
  - Hệ quả: lần 3 không còn "chỉ đổi độ dài dữ liệu"; độ dài làm đổi luôn hình dạng reward. Người dùng chọn sửa reward trước (2026-10-29).
- 🔧 **Reward thứ ba `sharpe` (Claude thiết kế 2026-10-29, người dùng cho sửa reward; giữ `gated` / `soft` để chạy lại được lần 1–2):**
  - `reward = 0.6 · s_sharpe + 0.4 · s_ic` (nhân `s_corr` như cũ); lỗi vẫn −10; không có cổng.
  - `s_sharpe = clip(Sharpe năm / 3.0, 0, 1)`, Sharpe tính như mọi nơi (`compute_metrics`, lợi suất ngày, √252); dưới 15 lệnh thì `s_sharpe = 0`. Lý do: kỳ vọng của Sharpe không đổi theo độ dài đoạn, còn MDD (mẫu số Calmar) tăng theo độ dài; proposal cũng lấy Sharpe năm làm thước đo chính. Mốc 3.0 lấy bằng `max_calmar` cũ, không chỉnh theo kết quả.
  - `s_ic = min(1, |IC| / 0.15)` như cũ, nhưng với template NORMALIZED, IC tính trên `ts_zscore(alpha, cửa sổ z)` — đúng tín hiệu được giao dịch — thay vì giá trị thô. RATIO / BOOLEAN giữ IC trên giá trị thô.
  - **Kiểm trước khi chạy `search` (chốt trước):** chấm đáp án bằng `sharpe` trên cả cách chia lần 2 và lần 3. Đạt nếu (1) reward trung bình của A trên đoạn học tăng theo IC ở cả hai cách chia, và (2) ở IC 0 hai cách chia cho reward trung bình chênh nhau không quá 0.1. Không đạt ⇒ báo người dùng, không tự chỉnh mốc.
  - ✅ Code (2026-10-29): `REWARD_MODES` thêm `"sharpe"`, `REWARD_WEIGHTS['max_sharpe'] = 3.0`, `MCTSEngine._ic_input`; oracle.csv thêm `reward_sharpe*`. Test 172 pass, 1 fail (có từ trước); cấy lỗi "dùng Calmar thay Sharpe" ⇒ 8 ca đỏ.
  - ⏸️ **Kết quả kiểm (oracle, 5 seed, IC 0 / 0.02 / 0.05 / 0.1; `results/planted_run2_sharpe/`, `results/planted_run3/`):**

    | Reward trên đoạn học | IC 0 | 0.02 | 0.05 | 0.1 |
    |---|---|---|---|---|
    | lần 2, soft | 0.32 ± 0.33 | 0.47 | 0.58 (cách 0.8 độ lệch) | 0.78 (1.4) |
    | lần 2, sharpe | 0.29 ± 0.21 | 0.38 | 0.50 (1.0) | 0.67 (1.8) |
    | lần 3, soft | 0.05 ± 0.02 | 0.03 | 0.07 | 0.23 |
    | lần 3, sharpe | 0.15 ± 0.08 | 0.16 | 0.24 (1.2) | 0.49 (4.2) |

    ("cách x độ lệch" = (trung bình − trung bình IC 0) / độ lệch giữa seed ở IC 0.)
    - (1) Tăng theo IC ở cả hai cách chia: **đạt**.
    - (2) Chênh ở IC 0 ≤ 0.1: **trượt** (0.29 vs 0.15, chênh 0.15).
    - Giải thích của Claude: ở IC 0, reward của A chỉ là nhiễu, lại lấy tốt nhất qua 5 ngưỡng z × 2 chiều và |IC|, nên mức của nó tỷ lệ với sai số ≈ 1/√số bar. Dự đoán theo tỷ lệ đó: 0.29 × √(1.738 / 4.831) ≈ 0.18, đo được 0.15. Tức là phần chênh còn lại đúng là "mức hên giảm khi có thêm dữ liệu" — thứ lần 3 muốn đo — chứ không phải lỗi thang đo; tiêu chí (2) do Claude đặt đã sai cách. Theo luật đã ghi, không tự đổi tiêu chí: chờ người dùng quyết. Người dùng cho chạy lần 3 (2026-10-29).
  - Lần 3 chạy với `sharpe`; để so công bằng, chạy thêm lần 2 bằng `sharpe` (cùng cách chia lần 2) nếu thời gian máy cho phép — ghi riêng.
- **Kết quả lần 3 (2026-10-29, sharpe, 20 lượt, mỗi lượt 3.210–3.990 s, tổng ≈ 2 giờ 10 phút trên 10 tiến trình; `results/planted_run3/`):**

  | IC mục tiêu | IC đo đoạn tìm | tìm lại đúng | tìm lại gần | Sharpe ngoài mẫu (2024) | lần 2: gần / Sharpe |
  |---|---|---|---|---|---|
  | 0 | −0.004 | 0/5 | 0/5 | −0.30 ± 1.14 | 0/5 / −2.17 |
  | 0.02 | 0.013 | 0/5 | 0/5 | −0.33 ± 0.52 | 0/5 / 0.12 |
  | 0.05 | 0.043 | 1/5 | 1/5 | −0.05 ± 1.14 | 1/5 / −0.65 |
  | 0.1 | 0.093 | 1/5 | **5/5** | 1.13 ± 0.97 | 3/5 / 0.74 |

  - ⛔ Tiêu chí IC 0.05 vẫn trượt (1/5); IC 0 đạt (0/5).
  - So với dự đoán chốt trước: ủng hộ một nửa. IC 0.1 tăng 3/5 → 5/5 (ngưỡng phát hiện tụt xuống giữa 0.05 và 0.1); IC 0.05 không tăng (1/5), thấp nhất trong khoảng dự đoán 1–3/5.
  - Ở IC 0.05, công thức gần A (|Spearman| ≥ 0.7) chỉ có trong ≤ 100 ứng viên ở 1/5 seed (lần 2: 2/5) ⇒ chặng nghẽn vẫn là đoạn học. IC đo được trên đoạn tìm của 5 seed chỉ 0.021–0.063.
  - Placebo tốt hơn hẳn: top-5 ở IC 0 lỗ ngoài mẫu ít hơn (−0.30 so với −2.17).
  - Lần 3 đổi cả độ dài dữ liệu lẫn reward nên chưa tách được phần nào do dữ liệu; muốn tách cần chạy lần 2 bằng `sharpe`.
- **Tách tác động (2026-10-29, người dùng cho chạy): lần 2 bằng `sharpe`** (cùng cách chia, A, blueprint, seed như lần 2; 20 lượt, mỗi lượt ≈ 1.820–2.040 s; `results/planted_run2_sharpe/`). Tìm lại gần / Sharpe ngoài mẫu:

  | IC | lần 2 soft (dữ liệu ngắn) | lần 2 sharpe (dữ liệu ngắn) | lần 3 sharpe (dữ liệu dài) |
  |---|---|---|---|
  | 0 | 0/5 / −2.17 | **2/5** / −0.49 | 0/5 / −0.30 |
  | 0.02 | 0/5 / 0.12 | 1/5 / 0.40 | 0/5 / −0.33 |
  | 0.05 | 1/5 / −0.65 | 1/5 / −0.49 | 1/5 / −0.05 |
  | 0.1 | 3/5 / 0.74 | 3/5 / −0.23 | **5/5** / 1.13 |

  - Đổi reward (cột 1 → 2): không tăng tỷ lệ tìm lại ở IC 0.05 / 0.1; ở IC 0 báo "tìm thấy" 2/5 (⛔ tiêu chí IC 0 trượt với dữ liệu ngắn). Seed 4 ở IC 0: placebo tình cờ có IC của A = 0.051, nên công thức gần A thắng là bắt đúng một quan hệ có thật trong bộ đó, không phải bịa.
  - Thêm dữ liệu (cột 2 → 3): IC 0.1 3/5 → 5/5, IC 0 2/5 → 0/5 ⇒ phần cải thiện của lần 3 chủ yếu do dữ liệu, không do reward. IC 0.05 không đổi ở cả ba cấu hình.
  - Lưu ý: 5 seed mỗi ô; chênh 3/5 vs 5/5 chưa có ý nghĩa thống kê (ước của Claude, chưa kiểm định). Sharpe ngoài mẫu lần 2 chỉ trên 6 tháng nên rất nhiễu.

## 11. Cách chia cửa sổ 1 walk-forward (số luận văn dùng)

Thiết lập (2026-10-30, `results/planted_window1/`): học 2018-08-13 → 2021-06-30 (3.583 bar), kiểm định 2021-07 → 2022-06, đánh giá 2022-07 → 2022-12; ngữ pháp có lan chiều (`c0e83a0`); bộ 20 blueprint mới (`results/blueprint_sets/20261029_212813/`); reward `sharpe`; 20 blueprint × 5.000 vòng; IC 0 / 0.05 / 0.1 × seed 1–5 = 15 lượt, mỗi lượt 2.370–3.340 s (≈ 2 giờ trên 10 tiến trình).

- **A:** `ts_zscore(ts_zscore(high − close, 10) − ts_zscore(close − close, 10), 10)`, NORMALIZED, từ OrderFlowSkewnessSignal; bỏ SkewnessKineticEnergySignal vì điền ra hằng (điều khoản mục 3). Thực chất A = z-score của `ts_zscore(high − close, 10)`. 1/20 blueprint biểu diễn được.
- **Chấm đáp án (`oracle.csv`, 54 s):** IC đo đoạn tìm trung bình −0.002 / 0.044 / 0.098.

| IC mục tiêu | IC đo đoạn tìm | IC đo đoạn đánh giá | tìm lại đúng | tìm lại gần | Sharpe ngoài mẫu |
|---|---|---|---|---|---|
| 0 | −0.003 | −0.025 | 0/5 | 0/5 | −0.90 ± 0.46 |
| 0.05 | 0.048 | 0.021 | 0/5 | 1/5 | −0.67 ± 1.52 |
| 0.1 | 0.098 | 0.068 | 1/5 | 1/5 | +0.21 ± 1.47 |

- IC 0: 0/5 tìm nhầm. IC 0.05: 1/5 (như mọi lần trước). **IC 0.1: chỉ 1/5**, thấp hơn hẳn lần 3 (5/5, 4.831 bar) và lần 2 (3/5, 1.738 bar), dù số bar học nằm giữa hai lần đó.
- Ở IC 0.1, công thức trùng A (|Spearman| = 1.0) **có** trong ≤ 100 ứng viên ở 2/5 seed: seed 5 đứng hạng 1 cả học lẫn kiểm định (tìm lại đúng); seed 3 hạng học 54 → hạng kiểm định 24, không vào top-5. Seed 1 có ứng viên tương quan 0.80 (hạng học 30 → kiểm định 48). ⇒ Lần này nghẽn ở cả đoạn học lẫn bước chọn trên đoạn kiểm định.
- Seed 5 ở IC 0.1 tìm lại đúng A nhưng Sharpe ngoài mẫu −1.94: IC của A trên 6 tháng đánh giá chỉ 0.081 và nhiễu 6 tháng lớn.
- IC 0 seed 5: một công thức trùng A đứng hạng 87 dù không cài gì; A chỉ là một công thức trong không gian tìm, và trong placebo đó nó tình cờ không tệ.
- Lượt chấm lỗi (−10) ≈ 7% mỗi lượt (`Input array/series must be 1D, got shape ()`, biểu thức toàn hằng; nợ ở ROADMAP mục 4).
- **Chưa tách được nguyên nhân tụt ở IC 0.1.** So với lần 3, lần này đổi cùng lúc: độ dài dữ liệu, ngữ pháp (lan chiều), công thức A, bộ blueprint. Suy đoán của Claude (chưa đo): A mới là tín hiệu hình dạng nến (`high − close`), tự tương quan thấp hơn A cũ (`ts_max − ts_mean` của giá), nên cùng IC thì Sharpe của tín hiệu và độ tách khỏi nhiễu khác; 5 seed mỗi ô nên 1/5 với 3/5 chưa chắc khác nhau thật. Chờ người dùng quyết có đo tách hay không.
- **Đo tách (2026-10-30, người dùng cho làm (a) rồi (b)):**
  - (a) Chọn top-5 theo hạng đoạn học thay vì đoạn kiểm định (tính lại từ `runs.csv`, chỉ xét ứng viên gần A nhất của mỗi lượt): IC 0.1 vẫn 1/5 (seed 5, hạng học 1); IC 0.05 thành 1/5 tìm lại đúng (seed 5: A hạng học 2, hạng kiểm định 23). ⇒ Bước chọn trên đoạn kiểm định không gây ra phần tụt; ở IC 0.1 ứng viên gần A (tương quan ≥ 0.74) có ở 4/5 seed nhưng hạng học 30 / 54 / 72 — nghẽn ở reward trên đoạn học.
  - Điểm `sharpe` của chính A trên đoạn học ở IC 0.1 (oracle): trung bình 0.39 (0.30–0.61); công thức tốt nhất MCTS tìm được 0.58–0.65. Lần 3 (A cũ): 0.49.
  - ~~Số lệnh của A (cột `trades` của `oracle.csv`) ≈ 2.730 / ≈ 4.830 bar ⇒ A mới quay vòng gấp ≈ 3 lần A cũ.~~ Sai: đếm trực tiếp vị thế của A (ngưỡng z tốt nhất trên đoạn học) chỉ đổi 573 lần (IC 0.1 seed 1, z 2.0, đứng ngoài 94% số bar) và 1.049 lần (seed 5, z 1.5, ngoài 87%), trong khi cột `trades` ghi 1.908 và 2.963; chỉ khớp ở z 0.5 (IC 0 seed 2: 2.904 / 2.903). ⛔ Câu hỏi mở: cột `trades` của oracle đo gì (trung bình ba độ mạnh gần như bằng nhau, 2.730,4 / 2.730,8 / 2.730,6, cũng đáng ngờ); chưa kiểm. So quay vòng A mới / A cũ chưa có số đúng.
  - (b) ✅ Thêm seed 6–10 ở IC 0.1 (ghi chung `runs.csv`, log `search_extra.log`; mỗi lượt 1.236–1.283 s): **tìm lại gần 5/5**, tìm lại đúng 0/5. Hạng học của ứng viên gần A 27 / 1 / 14 / 76 / 11 → hạng kiểm định 3 / 5 / 16 / 4 / 7 (bước kiểm định kéo lên). Sharpe ngoài mẫu −2.25 / −2.36 / 0.12 / −0.72 / 3.15.
  - **Gộp 10 seed ở IC 0.1: tìm lại gần 6/10, tìm lại đúng 1/10, Sharpe ngoài mẫu −0.10 ± 1.82.** ⇒ 1/5 của seed 1–5 phần lớn là nhiễu do ít seed; 6/10 không khác được lần 2 (3/5) hay lần 3 (5/5). Kết luận "nghẽn do phí của A mới" ở trên không được dữ liệu ủng hộ. Sharpe ngoài mẫu 6 tháng rất nhiễu: tìm lại gần mà vẫn −2.3.

## 4. Chạy

- MCTS trên đoạn tìm, rồi gộp top-5 trọng số đều, giao dịch trên đoạn đánh giá. Đây là đúng đơn vị đánh giá của proposal.
- **Ngân sách [đề xuất]:** 5.000 lượt lặp mỗi blueprint, 5 seed mỗi độ mạnh ⇒ 20 lượt chạy. Ước 20–40 phút trên máy này (chưa đo).
- Không chạy HMM: bài này không cần.

## 5. Đo và tiêu chí

**Kiểm tra "đáp án" trước khi chạy MCTS [đề xuất, thêm 2026-10-28 sau câu hỏi của người dùng về reward]:** chấm thẳng công thức cài bằng `MCTSEngine.evaluate_expression` trên đoạn tìm, ở từng độ mạnh. Lý do: reward có cổng cứng (−10 nếu Calmar < 1.1 hoặc < 15 lệnh). Nếu chính đáp án cũng nhận −10 thì reward không "cảm" được tín hiệu, và MCTS chỉ đang mò trong một mặt phẳng toàn −10. Khi đó lỗi nằm ở reward, không ở bước tìm. Ghi thêm tỷ lệ ứng viên nhận −10 trong mỗi lượt chạy.

**So hai bản reward (người dùng chốt 2026-10-28):** chấm đáp án bằng cả bản "gated" và bản "soft" (định nghĩa ở ROADMAP mục 3), ở IC 0 / 0.01 / 0.02 / 0.05. Chọn bản mà điểm đáp án tăng theo IC và tách khỏi điểm ở IC 0; nếu cả hai đều được thì chọn "soft" vì mặt reward mượt hơn cho MCTS. Lượt MCTS của bài này chạy với bản đã chọn; bản đó đóng băng cho walk-forward.

✅ **Kết quả chấm đáp án (2026-10-28, `results/planted/oracle.csv`, β hiệu chỉnh theo trung bình 20 hoán vị):** cả hai bản đều tăng theo IC. Soft: trung bình 0.075 / 0.143 / 0.215 / 0.31 ở IC 0 / 0.01 / 0.02 / 0.05. Gated: số seed qua cổng 1 / 2 / 3 / 4 trên 5. Hai nhóm chồng lấn (IC 0 seed 3 được 0.226 ở cả hai bản, là nhiễu placebo). Theo luật chốt trước ("cả hai được thì chọn soft") ⇒ **chọn "soft"**.

Mỗi (độ mạnh, seed) ghi:
- IC thực tế của tín hiệu cài trên đoạn tìm và đoạn đánh giá.
- **Tìm lại đúng:** có alpha trong top-5 có cùng cấu trúc và trường dữ liệu với công thức cài, cửa sổ lệch không quá một nấc trong `BASE_PERIODS` đã quy đổi.
- **Tìm lại gần:** tương quan Spearman giữa alpha tìm được và `A` trên đoạn tìm ≥ 0.7.
  - |Spearman| tính trên giá trị thô của biểu thức (trước z-score, ngưỡng, chiều của template). Luận văn báo kèm phân bố tương quan vì mốc 0.7 là quy ước (mốc 0.8 ⇒ IC 0.1 ở cửa sổ 1 còn 4/10).
  - ✅ **So thêm vị thế** (người dùng đổi ý 2026-10-30, trước đó đã chốt chỉ so giá trị thô vì đọc nhầm): với từng lượt, so vị thế của top-5 (mỗi ứng viên với tham số template của nó) với vị thế của A (ngưỡng z và chiều tốt nhất trên đoạn học) trên đoạn tìm: tương quan vị thế (Pearson) và tỷ lệ bar cùng dấu trong các bar có ít nhất một bên vào lệnh. Chạy lại 20 lượt cửa sổ 1 bằng cùng seed để lấy tham số template (`runs.csv` không lưu); 20/20 lượt cho lại đúng `closest_corr`. Kết quả: `results/planted_window1/positions_vs_a.json`.
    - Mốc nhiễu (IC 0): tương quan vị thế tốt nhất trong top-5 −0.09 … 0.13 (trung bình 0.03); cùng dấu khi có lệnh 1–7%.
    - IC 0.1, 6 lượt tìm lại gần: 0.72 / 0.25 / 0.66 / 0.04 / 0.46 / 0.52 (seed 5–10); cùng dấu khi có lệnh 15–59%. IC 0.05 seed 5 (tìm lại gần): 0.78.
    - Giá trị thô giống (tương quan 0.97) nhưng vị thế giống ít hơn nhiều (seed 6: 0.25), vì ngưỡng z khác nhau: A đứng ngoài 87–98% số bar, ứng viên thường vào lệnh nhiều hơn. Seed 8 (giá trị thô 0.74) có vị thế gần như không liên quan (0.04).
    - Nếu lấy "vị thế > mốc nhiễu lớn nhất 0.13" (mốc đặt sau khi xem số, chỉ để tham khảo): IC 0 / 0.05 / 0.1 = 0/5 / 2/5 / 6/10 (seed 8 rớt, seed 3 vào: một ứng viên giá trị thô 0.50 có vị thế 0.38).
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
