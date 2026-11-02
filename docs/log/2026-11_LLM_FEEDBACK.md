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

## 2026-11-01 — chạy thử lần 2 sau khi chặn 16.384 token + thử lại 2 lần (commit `6719dc9`)

**Chạy:** cùng 10 lượt placebo như lần 1 (2 bộ × cửa sổ 1, 3, 5, 6, 7, 10 worker), song song với RQ1 thật (4 worker); thư mục `results/smoke2_20261101/`, 20:51 → 21:54. Cùng tiêu chí đặt trước.

**Qua cả 5 tiêu chí.** 0/10 lượt rơi về; 0 hết giờ; 0 tràn ngữ cảnh còn sót sau thử lại; mọi blueprint mới biên dịch được (theo định nghĩa: chỉ blueprint qua trình biên dịch mới được nhận); `walkforward summary` in đủ tỉ lệ rơi về, lý do loại, số lần thử lại.

| | Số |
|---|---|
| Blueprint mới mỗi lượt | 10 ở 7 lượt, 9 ở 2 lượt, 6 ở 1 lượt |
| Lượt cần thử lại | 4/10; 6 lần bị cắt (`context_length`) trên 16 lần gửi yêu cầu đầu ⇒ ≈ 38 % mỗi lần |
| Lượt dùng hết 3 lần | 2/10 (lần thứ 3 qua) |
| Ý tưởng bị loại ở câu trả lời đầu | no_slot 6, khác 4, sai chiều 3, sai số đối số 2 |
| Còn bị loại sau sửa lỗi | no_slot 4, toán tử lạ 1, khác 1 |
| Thời gian LLM mỗi lượt | 277–2.183 s (có xếp hàng) |
| Thời gian mỗi lượt | 1.404–3.770 s |

**Ước (suy đoán, Claude, 2026-11-01):** nếu mỗi lần bị cắt độc lập với xác suất ≈ 0,38 thì ≈ 0,38³ ≈ 5 % lượt rơi về ⇒ ≈ 7/133 lượt placebo; dưới ngưỡng 1/10 đặt trước. Số thật đọc từ `summary` khi chạy xong.

**Chạy dài bắt đầu 2026-11-01 ≈ 22:00:**
- Placebo 133 lượt, 6 worker, `results/walkforward/llm_mcts/`, log `results/logs/placebo_llm_mcts_rerun.log`. Bản hỏng chuyển sang `results/walkforward/llm_mcts_broken_20261101/`.
- 90 ô LLM + MCTS của RQ1, 4 worker, thư mục riêng `results/planted_rq1_llm/` (chép `calibration.json`, `planted_formulas.json`, `segments.json`, `coverage.json` từ `results/planted_rq1/`) để không ghi chung `runs.csv` với RQ1 thật đang chạy. Khi cả hai xong: bỏ 90 dòng `llm_mcts` hỏng khỏi `results/planted_rq1/` (giữ bản lưu) và ghép dòng mới vào.
- Ước ≈ 14 giờ cho cả hai (suy đoán từ 10 lượt / 3.770 s; hàng đợi Ollama là nút thắt).

## 2026-11-02 — 90 ô LLM + MCTS của RQ1 chạy lại xong

22:00 → 12:35 (14,6 giờ, 4 worker, chung hàng đợi Ollama với placebo 6 worker). 3/90 rơi về (ước trước ≈ 5 %). Ghép vào `results/planted_rq1/`: bỏ 90 dòng `llm_mcts` cũ khỏi `runs.csv` và 600 dòng khỏi `checkpoints.csv`, nối dòng mới từ `results/planted_rq1_llm/`; bản trước khi ghép ở `results/planted_rq1/broken_llm_20261101/`. Số: [RESULTS](../RESULTS.md#bài-cài-tín-hiệu-rq1-hệ-thống-có-phản-hồi-bộ-rq1).

## 2026-11-02 — placebo chạy lại xong

21:56 → 14:11 (16 giờ 15 phút; ước trước ≈ 14 giờ, chậm hơn vì chung hàng đợi Ollama với RQ1 tới 12:35). 8/133 lượt rơi về (ước trước ≈ 7/133). Số: [RESULTS](../RESULTS.md#placebo-walk-forward-hệ-thống-có-phản-hồi-bộ-rq1).

## 2026-11-02 — review phương pháp trước khi đóng băng (agent Opus, chỉ đọc)

Người dùng giữ thiết kế, nhờ review; giả thuyết của người dùng: phần lớn công sức đến từ MCTS. Claude kiểm lại 5 điểm trên tệp kết quả (đánh dấu ✔); phần còn lại là số agent tính, chưa kiểm lại.

1. ✔ "A ngoài vùng blueprint" chỉ đúng về cấu trúc: `sub(?, ?)` (OpenCloseSpread) điền được A − hằng cho mọi A. Ô llm_mcts IC 0.1 A3 seed 10 có `(ts_argmin(volume, 10) - 2.0)` trong top-5 ở 10.000 vòng. `coverage.json`, dòng "A1, A2, A3 nằm ngoài vùng" ở RESULTS và Bảng 4.5 trên web đọc sai.
2. ✔ Lợi thế ở A kinh điển nằm hết ở A2 và phụ thuộc ngưỡng 0.7. IC 0.1, 100.000 vòng, gộp A1 + A2: ngưỡng 0.7 llm_mcts 7 / mcts_only 3 / random 4 (trên 20); 0.8: 3 / 2 / 3; 0.9: 1 / 0 / 3. A2 của llm_mcts: 5/10 → 1/10 → 0/10.
3. ✔ RQ1 chia đoạn theo mặc định `Segments()` (học 2018-08-13 → 2019-12-31, kiểm định tới 2020-06-30, đánh giá tới 2020-12-31), không phải cửa sổ 1 walk-forward như LLM_FEEDBACK ghi.
4. ✔ `WalkForward.summarize`: chuỗi thật = trung bình 5 seed mỗi ngày, mỗi bộ placebo = 1 seed ⇒ hai phân phối không cùng phép đo. Ảnh hưởng lên p chưa đo.
5. ✔ MCTS không LLM thu hẹp bảng xếp hạng: trung vị số biểu thức khác nhau 95 (10.000) → 30 (100.000); llm_mcts 96 → 86, random 96 → 97.
6. Lần đầu chạm A đo theo khối 500 vòng; llm_mcts xoay vòng 20 blueprint nên không dùng được để nói "nhanh hơn".
7. Nguồn top-5 cuối của llm_mcts (RQ1): 51 % chỉ từ blueprint ban đầu, 36 % chỉ từ blueprint phản hồi, 13 % cả hai. Vòng phản hồi đổi công thức được chọn, không tăng số lần tìm lại A (11 ô gần ở 50.000 → 10 ở 100.000).
8. Placebo llm_mcts: top-5 gần như toàn NORMALIZED (661/665), hệ thống sinh một lần 319 NORMALIZED / 346 BOOLEAN; suy đoán đây là lý do số lệnh 343 → 48.
9. Không thấy rò rỉ giữa các đoạn. Random tiêu ≈ 39 % ngân sách vào mẫu trùng mà vẫn ngang hai cấu hình kia.

Kết luận của agent (chưa phải của luận văn): vòng phản hồi không thêm gì ròng; MCTS không hơn lấy mẫu ngẫu nhiên cùng ngữ pháp; khác biệt chủ yếu từ bộ blueprint ban đầu và bước chọn trên bảng xếp hạng / đoạn kiểm định.
