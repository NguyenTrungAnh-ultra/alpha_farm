# Vòng phản hồi LLM và RQ1

Phương pháp như sẽ làm (chưa code). Quyết định: [DECISIONS](../DECISIONS.md#câu-hỏi-nghiên-cứu-và-quy-tắc-chung). Trạng thái: [PLAN](../PLAN.md). Công trình liên quan: [RELATED_WORK](RELATED_WORK.md). Dòng có ⏸️ là đề xuất của Claude, chờ người dùng chốt.

## Câu hỏi

- **RQ1 (chính):** có LLM trong vòng tìm kiếm thì quy trình phát hiện được tín hiệu yếu hơn không, so với cùng ngân sách mà không có LLM? Đo bằng bài cài tín hiệu chạy cho từng cấu hình.
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
| Tìm ngẫu nhiên | 100.000 công thức hợp lệ về chiều, sinh đều theo ngữ pháp, cùng độ sâu | ✅ | ✅ |
| LLM không tìm | LLM viết công thức hoàn chỉnh (không `?`), chấm hết số viết được | — (LLM không thấy dữ liệu, không có gì để tìm lại) | ✅, kiêm kiểm tra rò rỉ |
| Mua và giữ, TSMOM | tham chiếu | — | ✅ |

## Bài cài tín hiệu cho RQ1

- Cách chia cửa sổ 1, 10 seed mỗi ô, IC 0 / 0.05 / 0.1; IC 0 không cài gì nên dùng chung cho mọi A.
- **Bốn A, chốt trước khi chạy:**
  - 2 kinh điển: ⏸️ hồi quy về trung bình `ts_zscore(close, 10)` đổi dấu; động lượng `ts_mean(sub(close, open), 10)`.
  - 2 lạ: công thức sinh ngẫu nhiên theo ngữ pháp, seed 1 và 2; bỏ biểu thức hằng và biểu thức có |Spearman| ≥ 0.7 với A kinh điển, rồi lấy công thức hợp lệ kế tiếp.
  - Mọi A phải biểu diễn được ở độ sâu 4 và không trùng nguyên văn blueprint nào.
- **Thước đo chính:** tỉ lệ tìm lại gần (|Spearman| ≥ 0.7 trong top-5) theo cấu hình × A × IC; so LLM + MCTS với từng cấu hình khác bằng Fisher ở cùng ô. **Phụ:** số lượt chấm tới lần đầu chạm A; độ phủ toán tử của blueprint mới so với blueprint ban đầu.
- Đọc: thắng ở cả hai loại A ⇒ LLM giúp tìm nói chung; thắng kinh điển, thua lạ ⇒ LLM là định kiến về dạng quen; không thắng ⇒ mô hình 4B không góp vào độ nhạy.
- 10 seed chỉ phân biệt được chênh lớn (cỡ 6/10 với 1/10); ghi kèm kết quả.

## Thứ tự và thời gian máy

1. Code: vòng phản hồi, MCTS không LLM, tìm ngẫu nhiên, chọn A, sửa prompt. Test cho mỗi phần.
2. Sinh lại bộ blueprint; đóng băng bộ mới.
3. **Đo một lượt có phản hồi** (thời gian LLM, thời gian MCTS) và thử `OLLAMA_NUM_PARALLEL`. Ước thô: 10 blueprint ≈ 10–20 phút LLM mỗi lượt (lần sinh 20 blueprint mất 37 phút) — chưa đo.
4. Bài cài tín hiệu RQ1: LLM + MCTS 90 lượt (4 A × 2 IC × 10 + 10 ở IC 0), MCTS không LLM 90, tìm ngẫu nhiên 90.
5. Placebo chạy lại trên hệ thống có phản hồi: 19 × 7 = 133 lượt.
6. Đóng băng → chạy thật một lần (mọi cấu hình, 5 seed).

Riêng phần LLM, nếu Ollama xử lý từng yêu cầu một: 90 + 133 + 35 lượt × 10–20 phút ≈ 43–86 giờ. Bước 3 quyết định có giữ được thiết kế này không; quá đắt ⇒ phương án lùi: giữ sinh một lần, RQ1 hỏi giá trị của bộ khung vạch sẵn.

## Ngoài phạm vi

Nhiều vòng phản hồi, LLM thấy dữ liệu thô, mô hình khác 4B (hướng phát triển).
