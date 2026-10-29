# Thiết kế — Walk-forward trên dữ liệu thật (Tháng 2)

Bản hiện hành. Đổi ý thì sửa đúng chỗ, kèm một dòng lý do + ngày.
Trạng thái: ⏸️ bản nháp của Claude (2026-10-29), chờ người dùng duyệt trước khi code. Các quyết định đã chốt ở `docs/ROADMAP.md` mục 3 (2026-10-29); chỗ ghi **[đề xuất]** là của Claude, chưa ai chốt.

## 1. Câu hỏi

Chạy quy trình tìm alpha như thể đứng ở từng thời điểm trong quá khứ: chỉ thấy dữ liệu trước thời điểm đó, chọn top-5, giao dịch 6 tháng kế tiếp. Ghép các đoạn 6 tháng thành một chuỗi lợi suất ngày ngoài mẫu 2022-07 → 2025-12. Sharpe năm của chuỗi đó là thước đo chính cho RQ1 và RQ2 (proposal mục "Walk-forward"; RQ2 cũ về chỉ báo kỹ thuật đã bỏ, RQ3 cũ đánh số lại thành RQ2, `docs/ROADMAP.md` mục 3, 2026-10-29).

## 2. Cửa sổ

- Nở dần từ 2018-08-13 (người dùng chốt 2026-10-29). Khung 60m (tệp `1H`, không thiếu ngày); khung phút để sau khi xử lý nợ 126 ngày thiếu.
- **[đề xuất]** Đoạn kiểm định cố định **12 tháng** ngay trước đoạn đánh giá; đoạn học là toàn bộ phần trước đó. Lý do: lăn đều 6 tháng một, đoạn kiểm định đủ dài hơn hẳn 6 tháng của lần 2 (quá nhiễu). Lần 3 của bài cài tín hiệu dùng 18 tháng; 12 tháng cho đoạn học cửa sổ đầu dài hơn.

| Cửa sổ | Học | Kiểm định | Đánh giá | Bar học / kiểm định / đánh giá |
|---|---|---|---|---|
| 1 | 2018-08-13 → 2021-06-30 | 2021-07 → 2022-06 | 2022-07 → 2022-12 | 3.583 / 1.248 / 645 |
| 2 | → 2021-12-31 | 2022-01 → 2022-12 | 2023-01 → 2023-06 | |
| 3 | → 2022-06-30 | 2022-07 → 2023-06 | 2023-07 → 2023-12 | |
| 4 | → 2022-12-31 | 2023-01 → 2023-12 | 2024-01 → 2024-06 | |
| 5 | → 2023-06-30 | 2023-07 → 2024-06 | 2024-07 → 2024-12 | |
| 6 | → 2023-12-31 | 2024-01 → 2024-12 | 2025-01 → 2025-06 | |
| 7 | → 2024-06-30 | 2024-07 → 2025-06 | 2025-07 → 2025-12 | ≈ 6.700 / 1.250 / 650 |

(Số bar các hàng 2–7 điền khi code tính; cửa sổ 1 đếm 2026-10-29.)

- Độ nhạy: đoạn học cửa sổ 1 (3.583 bar) nằm giữa lần 2 (1.738) và lần 3 (4.831) của bài cài tín hiệu. **[đề xuất]** Trước lần chạy thật, chạy bài cài tín hiệu đúng cách chia của cửa sổ 1 (IC 0 / 0.05 / 0.1, `sharpe`, ≈ 1,5 giờ) để biết độ nhạy của cửa sổ yếu nhất; luận văn báo cáo kèm.

## 3. Mỗi cửa sổ làm gì (giống bài cài tín hiệu lần 3)

1. MCTS trên đoạn học, reward `sharpe`, 20 blueprint × 5.000 vòng (ngân sách 100.000 lượt chấm).
2. Tối đa 100 biểu thức khác nhau tốt nhất → chấm lại trên đoạn kiểm định → top-5.
3. Vị thế top-5 trọng số đều, giao dịch trên đoạn đánh giá (phí, ký quỹ như `AlphaBacktestEngine`); lịch sử chỉ báo lấy từ khung liên tục nên không mất phần khởi động.
4. Ghi lợi suất ngày của đoạn đánh giá, top-5 (biểu thức + tham số template + chiều), reward học / kiểm định.
5. Mỗi cấu hình chạy 5 seed (1–5).

## 4. Cấu hình so sánh (proposal bảng "Configurations compared")

Cùng ngân sách 100.000 lượt chấm mỗi cửa sổ, cùng bước 2–4.

| Cấu hình | Cách làm [đề xuất] | RQ | Có code chưa |
|---|---|---|---|
| LLM + MCTS | như mục 3 | 1, 3 | ✅ (ghép từ bài cài tín hiệu) |
| MCTS không có LLM | MCTS từ gốc là một ô `?` dưới template NORMALIZED, 100.000 vòng | 1 | ⛔ |
| LLM không tìm | LLM viết công thức hoàn chỉnh (không `?`); chấm hết số LLM viết được, không đủ 100.000 — ghi rõ là ngoại lệ về ngân sách | 1 | ⛔ |
| Tìm ngẫu nhiên | 100.000 công thức hợp lệ về chiều, sinh ngẫu nhiên đều theo ngữ pháp | 1 | ⛔ |
| Mua và giữ | luôn long | tham chiếu | dễ |
| TSMOM | momentum chuỗi thời gian (Moskowitz 2012), chuyển sang bar trong ngày | tham chiếu | ⛔ |

## 5. Placebo (RQ2)

- Lặp toàn bộ walk-forward của LLM + MCTS trên K = 19 bộ placebo: hoán vị lợi suất trong từng đoạn (học, kiểm định, đánh giá xáo riêng), như bài cài tín hiệu. Một seed mỗi bộ.
- p = tỷ lệ lần chạy (kể cả lần thật) có Sharpe ngoài mẫu ≥ lần thật; nhỏ nhất 1/20 = 0.05.
- **[đề xuất]** Ngân sách placebo bằng lần thật nếu thời gian máy cho phép (proposal cho phép giảm).

## 6. Đóng băng trước lần chạy thật (ROADMAP mục 3)

Ghi vào `results/walkforward/frozen.json` và commit trước khi chạy: reward `sharpe` + `REWARD_WEIGHTS`, bảng cửa sổ, tệp blueprint (hash), ngân sách, seed, khung, `MAX_RANKED`, `TOP_K`, commit git, dấu vân tay dữ liệu. Code từ chối chạy dữ liệu thật nếu cấu hình khác bản đóng băng.

- ✅ **Bộ blueprint: sinh lại bằng prompt mới rồi mới đóng băng** (người dùng chốt 2026-10-29 theo đề xuất của Claude). Lý do: bộ cũ có 2/20 blueprint chép nguyên ví dụ trong prompt, làm yếu RQ1. Bài cài tín hiệu ở mục 2 chạy trên bộ mới (chọn lại A theo đúng luật cũ ở `docs/PLANTED_SIGNAL.md` mục 3).
  - Sửa prompt: ẩn tên thị trường ("hợp đồng tương lai chỉ số, bar 60 phút", không ghi VN30 / Việt Nam) — cách kiểm số 1 của nợ rò rỉ qua trọng số LLM; đổi cách đưa ví dụ để giảm chép.
  - **Chỉnh prompt / tham số trước bằng lô nhỏ** (người dùng yêu cầu 2026-10-29: "sinh ít ít trước để test prompt / tham số … ổn rồi mới sinh thật"): mỗi cấu hình (biến thể prompt × tham số Ollama: temperature, top_p, …) sinh một lô nhỏ, đo tỷ lệ biên dịch được, tỷ lệ có `?`, tỷ lệ trùng ví dụ prompt, số khung khác nhau, số vòng tự sửa, thời gian. Chọn cấu hình rồi mới sinh bộ thật 20 blueprint và đóng băng cùng cấu hình đã chọn.
  - **Tiêu chí bộ thật (chốt trước):** 0 blueprint trùng nguyên văn ví dụ trong prompt; không có hai blueprint cùng khung (so cấu trúc cây, bỏ qua tên trường điền sẵn); mọi blueprint có ≥ 1 `?` và biên dịch được; mô hình 4B, 20 blueprint. 4B không đạt sau 5 lần sinh thật ⇒ thử `ollama-9b` (luật 2026-10-28).
  - Lô thử chỉ dùng để chọn prompt / tham số, không chấm trên dữ liệu nào, nên không đụng tới quy tắc dữ liệu thật.

## 7. Thời gian máy (ước, chưa đo)

Lần 3 bài cài tín hiệu: ≈ 3.600 s / lượt với 4.831 bar học, 10 lượt song song.

| Phần | Lượt | Ước thời gian thật |
|---|---|---|
| LLM + MCTS | 7 cửa sổ × 5 seed = 35 | ≈ 4 giờ |
| MCTS không LLM, tìm ngẫu nhiên | 2 × 35 = 70 | ≈ 8 giờ |
| Placebo | 19 × 7 = 133 | ≈ 14 giờ |

## 8. Code [đề xuất]

- `strategy_workflows/WalkForward.py` + `main.py walkforward <bước>`; dùng lại `rank_leaderboard`, `distinct_expressions`, `combine_positions`, `Segments` (chuyển các hàm dùng chung ra khỏi `RunPlantedSignal.py` nếu cần).
- Kết quả: `results/walkforward/<cấu hình>/runs.csv` (mỗi cửa sổ × seed một dòng, có tham số template của top-5) và `returns.csv` (lợi suất ngày ngoài mẫu).
- Thứ tự: (1) LLM + MCTS trên **placebo** trước để thử đường ống mà chưa chạm dữ liệu thật; (2) các cấu hình so sánh; (3) đóng băng; (4) chạy thật một lần.
- Web: thêm trang walk-forward sau khi có `runs.csv`.

## 9. Ngoài phạm vi lần này

SPA / DSR (Tháng 4), khung phút, kiểm tra rò rỉ qua trọng số LLM (nợ ở ROADMAP mục 4).
