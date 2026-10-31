# Vòng phản hồi LLM và RQ1

Phương pháp như sẽ làm (chưa code). Quyết định: [DECISIONS](../DECISIONS.md#câu-hỏi-nghiên-cứu-và-quy-tắc-chung). Trạng thái: [PLAN](../PLAN.md). Công trình liên quan: [RELATED_WORK](RELATED_WORK.md). Dòng có ⏸️ là đề xuất của Claude, chờ người dùng chốt.

## Câu hỏi

- **RQ1 (chính):** cùng giới hạn độ dài công thức, LLM đưa MCTS tới tín hiệu đúng sớm hơn hay chặn đường tới nó? Blueprint thu vùng tìm kiếm từ ≈ 1.9 × 10⁴¹ xuống ≈ 4.6 × 10¹⁴ công thức ([RESULTS](../RESULTS.md#không-gian-tìm-kiếm)); "sớm hơn" chỉ đúng khi tín hiệu nằm trong vùng đó. Ba câu con:
  - **(a) Sinh một lần:** tới A sớm hơn MCTS không LLM, hay bị chặn khi A nằm ngoài vùng blueprint? Đo ở mốc 50.000 lượt chấm (hết giai đoạn A, trước phản hồi).
  - **(b) Phản hồi:** khi bị chặn, sau khi thấy điểm đoạn học LLM có viết được blueprint mới chứa A (hoặc gần A) không? Đo ở 100.000.
  - **(c) Chi phí:** "sớm hơn" tính theo lượt chấm và theo thời gian thật (LLM tính cả).
- **RQ1 (mô tả):** Sharpe ngoài mẫu của các cấu hình trong lần chạy thật, kèm khoảng tin cậy của chênh lệch (dữ liệu chỉ phân biệt được chênh ≈ 1.0–1.25, [WALK_FORWARD](WALK_FORWARD.md#cấu-hình-so-sánh)).
- RQ2 giữ nguyên câu hỏi, chạy lại trên hệ thống có vòng phản hồi.

## Hệ thống LLM + MCTS có phản hồi

Mỗi lượt (một cửa sổ walk-forward hoặc một lượt bài cài tín hiệu), tổng 100.000 lượt chấm như cũ:

1. **Giai đoạn A:** 20 blueprint ban đầu (bộ đóng băng, sinh lại bằng prompt đã sửa) × 2.500 vòng MCTS = 50.000 lượt chấm, trên đoạn học.
2. **Phản hồi:** lấy 10 biểu thức khác nhau tốt nhất theo reward đoạn học; đưa LLM: biểu thức, reward, IC đoạn học. ⛔ đoạn kiểm định và đoạn đánh giá. Ẩn tên thị trường như prompt sinh ban đầu.
3. **LLM viết 10 blueprint mới** qua `generate_set` (cùng luật hợp lệ: biên dịch được, có `?`, không trùng khung với 20 blueprint ban đầu và với nhau). Phản hồi đưa vào qua tham số `experience`.
4. **Giai đoạn B:** 10 blueprint mới × 5.000 vòng = 50.000 lượt chấm.
5. Chọn top-5 như cũ: ≤ 100 biểu thức tốt nhất của cả hai giai đoạn → đoạn kiểm định → top-5.
6. Ghi lại 10 blueprint mới, prompt phản hồi (hash), thời gian LLM của từng lượt.

- ⏸️ Một vòng phản hồi, 10 blueprint mới, chia 50/50 ngân sách. Nhiều vòng hơn làm thời gian LLM tăng tuyến tính.
- ⏸️ Ollama `seed` cố định theo (lượt, seed MCTS) để chạy lại ra cùng blueprint; temperature 0.3 như lần sinh đầu.

## Sửa prompt

- Luật chiều của `mult` hiện ghi ví dụ "`ts_zscore(?)` hoặc `ts_rank(?)`" (`utilities/Prompts.py`, `DIMENSION_RULES`); bộ hiện tại có `ts_zscore` ở 16/20 blueprint. Đổi thành mô tả không kèm mảnh công thức ("một vế có chiều RATIO, xem bảng chiều").
- Sinh lại bộ 20 blueprint ban đầu theo cùng tiêu chí bộ thật ([WALK_FORWARD](WALK_FORWARD.md#bộ-blueprint)); thêm đo độ phủ toán tử. Bộ cũ `20261029_212813` chuyển thành lịch sử.

## Các cấu hình

| Cấu hình | Sinh ứng viên | Bài cài tín hiệu (RQ1 chính) | Walk-forward thật (mô tả) |
|---|---|---|---|
| LLM + MCTS có phản hồi | như trên | ✅ | ✅ |
| MCTS không LLM | MCTS từ một ô `?` dưới mỗi template NORMALIZED / BOOLEAN / RATIO, chia đều 100.000 lượt | ✅ | ✅ |
| Tìm ngẫu nhiên | 100.000 công thức hợp lệ về chiều, sinh theo kích thước (ramped half-and-half), cùng độ sâu | ✅ | ✅ |
| LLM không tìm | LLM viết công thức hoàn chỉnh (không `?`), chấm hết số viết được | — (LLM không thấy dữ liệu, không có gì để tìm lại) | ✅, kiêm kiểm tra rò rỉ |
| Mua và giữ, TSMOM | tham chiếu | — | ✅ |

## Bài cài tín hiệu cho RQ1

- Cách chia cửa sổ 1, 10 seed mỗi ô, IC 0 / 0.05 / 0.1; IC 0 không cài gì nên dùng chung cho mọi A.
- **Bốn A:** 2 kinh điển, 2 lạ, kích thước khớp nhau; cách chọn ở [Quy tắc chốt trước khi chạy](#quy-tắc-chốt-trước-khi-chạy).
  - Mọi A phải biểu diễn được ở độ sâu 4 và không trùng nguyên văn blueprint nào.
  - Với mỗi A ghi trước khi chạy: A có nằm trong vùng của bộ blueprint ban đầu không (blueprint nào điền ra được A), và số cách điền của blueprint nhỏ nhất chứa A (độ khó tìm trong vùng). Blueprint chứa A cũ chỉ có 400 cách điền ⇒ gần như duyệt hết; A mới nên nằm ở chỗ tìm thật sự khó.
- **Thước đo chính:** tỉ lệ tìm lại gần (|Spearman| ≥ 0.7 trong top-5) theo cấu hình × A × IC tại các mốc 10.000 / 25.000 / 50.000 / 75.000 / 100.000 lượt chấm (chụp bảng xếp hạng trong cùng lượt, không chạy thêm); so LLM + MCTS với MCTS không LLM bằng Fisher ở cùng ô và cùng mốc. **Phụ:** số lượt chấm và thời gian thật tới lần đầu chạm A; blueprint phản hồi có chứa A không; độ phủ toán tử của blueprint mới.
- Đọc theo A trong / ngoài vùng blueprint ban đầu:

| | A trong vùng | A ngoài vùng |
|---|---|---|
| Có LLM tới A sớm hơn | LLM rút ngắn đường | (không xảy ra ở mốc 50.000) |
| Có LLM chậm hơn hoặc không tới | vùng đúng nhưng xếp hạng / tìm trong vùng kém | **bị chặn**; nếu phản hồi mở được đường ở mốc 100.000 ⇒ phản hồi có giá trị |

- Tóm lại: thắng ở cả A kinh điển lẫn A lạ ⇒ LLM giúp tìm nói chung; thắng kinh điển, thua lạ ⇒ LLM là định kiến về dạng quen; không thắng ⇒ mô hình 4B không góp vào việc tìm.
- 10 seed chỉ phân biệt được chênh lớn (cỡ 6/10 với 1/10); ghi kèm kết quả.

## Quy tắc chốt trước khi chạy

⏸️ Toàn bộ mục này là đề xuất của Claude (2026-10-31), chờ người dùng duyệt.

1. **Chọn A trước khi sinh lại blueprint.** Ghi 4 A (biểu thức, chiều cài, seed sinh) vào DECISIONS và commit **trước** khi chạy sinh bộ blueprint mới; sau đó mới kiểm A trong / ngoài vùng. Kích thước khớp nhau để độ dài không lẫn vào kết luận:
   - A1 kinh điển: `ts_zscore(pv_close, 10)`, cài chiều âm (hồi quy về trung bình); 1 toán tử.
   - A2 kinh điển: `ts_mean(sub(pv_close, pv_open), 10)` (động lượng trong phiên); 2 toán tử.
   - A3 lạ: sinh ngẫu nhiên đúng 1 toán tử, seed 1. A4 lạ: đúng 2 toán tử, seed 2. Bỏ biểu thức hằng, |Spearman| ≥ 0.7 với A1 / A2, hoặc trùng dạng kinh điển; lấy biểu thức hợp lệ kế tiếp của cùng seed.
   - Báo kết quả theo từng A, không gộp thành một con số.
2. **Một phép so chính, còn lại là mô tả.** Chính: LLM + MCTS so với MCTS không LLM, IC 0.1, gộp theo loại A (A1 + A2 = 20 lượt, A3 + A4 = 20 lượt mỗi cấu hình), tại mốc 50.000 và 100.000 ⇒ 4 phép Fisher hai phía (LLM có thể chặn đường), chỉnh Holm. Mọi ô khác (IC 0.05, từng A, các mốc khác, tìm ngẫu nhiên) chỉ mô tả, không đọc p.
3. **Tìm ngẫu nhiên theo kích thước:** "ramped half-and-half" như GP: chia đều 100.000 mẫu cho độ sâu 1–4, mỗi độ sâu nửa cây đầy nửa cây mọc tự do; hợp lệ về chiều; cửa sổ và tham số template rút đều; bỏ biểu thức trùng.
4. **RQ2 theo từng A:** ngưỡng phát hiện của LLM + MCTS ở mốc 100.000 báo riêng cho từng A. Không A nào qua ở IC 0.1 ⇒ thêm mức IC 0.2 chỉ cho LLM + MCTS (luật đặt trước, không chọn sau khi xem).
5. **Ngưỡng dừng giờ máy:** đo một lượt có phản hồi, thử `OLLAMA_NUM_PARALLEL` 2–4. Ước tổng phần LLM > 48 giờ ⇒ giảm còn 5 blueprint phản hồi; vẫn > 48 giờ ⇒ bỏ phản hồi, chỉ trả lời câu (a) và (c).

## Thứ tự và thời gian máy

1. Code: vòng phản hồi, MCTS không LLM, tìm ngẫu nhiên, chọn A (kèm kiểm trong / ngoài vùng), chụp bảng xếp hạng theo mốc, sửa prompt. Test cho mỗi phần.
2. Chọn và commit 4 A; rồi sinh lại bộ blueprint, đóng băng bộ mới.
3. **Đo một lượt có phản hồi** (thời gian LLM, thời gian MCTS) và thử `OLLAMA_NUM_PARALLEL`. Ước thô: 10 blueprint ≈ 10–20 phút LLM mỗi lượt (lần sinh 20 blueprint mất 37 phút) — chưa đo.
4. Bài cài tín hiệu RQ1: LLM + MCTS 90 lượt (4 A × 2 IC × 10 + 10 ở IC 0), MCTS không LLM 90, tìm ngẫu nhiên 90.
5. Placebo chạy lại trên hệ thống có phản hồi: 19 × 7 = 133 lượt.
6. Đóng băng → chạy thật một lần (mọi cấu hình, 5 seed).

Riêng phần LLM, nếu Ollama xử lý từng yêu cầu một: 90 + 133 + 35 lượt × 10–20 phút ≈ 43–86 giờ. Bước 3 quyết định có giữ được thiết kế này không; quá đắt ⇒ phương án lùi: giữ sinh một lần, RQ1 hỏi giá trị của bộ khung vạch sẵn.

## Ngoài phạm vi

Nhiều vòng phản hồi, LLM thấy dữ liệu thô, mô hình khác 4B (hướng phát triển).
