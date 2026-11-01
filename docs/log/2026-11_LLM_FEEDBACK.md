# Nhật ký: vòng phản hồi LLM, 2026-11

Thiết kế: [design/LLM_FEEDBACK](../design/LLM_FEEDBACK.md). Trạng thái: [PLAN](../PLAN.md) việc 9c–9e.

## 2026-11-01 — lần chạy đầu: vòng phản hồi hỏng ở hơn nửa số lượt

**Chạy:** placebo `--system llm_mcts` (133 lượt, 10 worker, 10:04 → 18:40) song song với bài cài tín hiệu RQ1 (`rq1 search`, 4 worker, từ 10:13). Lần khởi động RQ1 đầu tiên (10:04) chết ở hiệu chỉnh β: `BrokenProcessPool`, không có traceback (log `results/logs/rq1_search_crash1.log`); chạy lại riêng bước đó 3 lần đều qua, chưa rõ nguyên nhân.

**Vòng phản hồi không sinh blueprint mới nào (`fallback`, rơi về bộ ban đầu cho 50.000 vòng còn lại):**

| | Lượt | Rơi về | Hết giờ 900 s, 0 ý tưởng | 0 ý tưởng, chưa tới 900 s | 10 ý tưởng, 0 biên dịch được |
|---|---|---|---|---|---|
| Placebo | 133 | 69 | 17 | 41 | 11 |
| RQ1, ô LLM + MCTS đã xong lúc 18:40 | 72 | 56 | 14 | 33 | 9 |

Lượt có phản hồi: số blueprint mới 1–10 (placebo: 42 lượt đủ 10).

**Gửi lại 3 prompt phản hồi** (dựng từ top-5 của 3 lượt placebo, cùng mô hình, `format: json`, `num_ctx` 16.384, có suy nghĩ; script ở scratchpad, không giữ trong repo):

| Lượt | Thời gian | Token prompt | Token sinh | `done_reason` | Kết quả |
|---|---|---|---|---|---|
| 1 | 235 s | 2.489 | 8.452 | stop | 10 ý tưởng |
| 5 | 545 s | 2.547 | 10.502 | stop | 10 ý tưởng, có `ts_argmax(pv_close, ?)` (cửa sổ viết thành đối số) |
| 9 | 296 s | 2.506 | 13.878 | **length** | trả lời rỗng: 2.506 + 13.878 = 16.384 = `num_ctx`, suy nghĩ ăn hết ngữ cảnh |

**Nguyên nhân (đã kiểm trên 3 yêu cầu, chưa kiểm hết 125 lượt hỏng):**
1. Suy nghĩ của mô hình dài 8–14 nghìn token, chạm `num_ctx` 16.384 trước khi viết JSON ⇒ `response` rỗng, client trả phần suy nghĩ ⇒ không có JSON.
2. Ollama xử lý từng yêu cầu một; 10 worker cùng hỏi ⇒ yêu cầu phải chờ nhiều lượt khác, vượt `BATCH_REQUEST_TIMEOUT_S` 900 s.
3. Prompt phản hồi liệt kê công thức tốt nhất ở dạng có cửa sổ (`ts_mean(close, 10)`); mô hình chép dạng hai đối số vào blueprint (`ts_argmax(pv_close, ?)`), trình biên dịch blueprint từ chối; yêu cầu sửa lỗi cũng không cứu được (suy đoán từ 1 câu trả lời).
4. Lỗi trong tiến trình con (`[blueprints] chat error`, `rejected`) không vào log: stdout của worker bị mất. `runs.csv` chỉ ghi `ideas` / `compiled`, không ghi lý do.

**Hệ quả:** placebo 133 lượt và 90 ô LLM + MCTS của RQ1 đo một hệ thống nửa có phản hồi nửa không ⇒ không dùng. Số của placebo này, chỉ để tham khảo: Sharpe 19 bộ trung bình −0.13, độ lệch chuẩn 0.62, từ −0.98 đến 1.43; số lệnh mỗi cửa sổ trung vị 54 (hệ thống sinh một lần: 343). Ô MCTS không LLM và tìm ngẫu nhiên của RQ1 không dùng LLM, để chạy tiếp.

## 2026-11-01 — chạy thử sau khi sửa (commit `415227e`)

**Chạy:** placebo 2 bộ × cửa sổ 1, 3, 5, 6, 7 = 10 lượt cùng lúc (10 worker), song song với RQ1 thử (`llm_mcts`, A4, IC 0.1, seed 1–2, 2 worker) và RQ1 thật (4 worker, ô MCTS không LLM / ngẫu nhiên); thư mục `results/smoke_20261101/`. Tiêu chí qua đặt trước: ≤ 1/10 lượt rơi về, 0 hết giờ, 0 tràn ngữ cảnh, mọi blueprint mới biên dịch được, hai lệnh `summary` đọc được.

**Placebo thử: trượt.** 4/10 lượt rơi về, cả 4 do tràn ngữ cảnh (`context_length`); 0 hết giờ; 6 lượt còn lại ra 6–10 blueprint mới, 10/10 ý tưởng biên dịch được ở 4 lượt (lỗi cú pháp cửa sổ đã hết). Một yêu cầu: prompt 2.727 + sinh 30.041 token ⇒ suy nghĩ có lúc chạy dài gấp ≈ 3 lần bình thường (8–14 nghìn token), không chỉ thiếu chỗ. Thời gian LLM mỗi lượt 678–2.723 s (xếp hàng), mỗi lượt 2.095–4.287 s khi máy chạy 16 tiến trình. `walkforward summary` in đúng tỉ lệ rơi về và lý do.

**RQ1 thử, ô đầu (seed 1):** 5 blueprint mới, 4/10 ý tưởng đầu biên dịch được; loại vì thiếu `?` 4, sai chiều 4 (mô hình chép nguyên công thức hoàn chỉnh từ phản hồi).
