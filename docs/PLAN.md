# Kế hoạch

Mỗi việc một dòng: là gì · trạng thái · tới đâu · tệp chi tiết. Quyết định ở [DECISIONS](DECISIONS.md), số đo ở [RESULTS](RESULTS.md), quá trình ở [log/](log/).
Khung nghiên cứu: `proposal/thesis_proposal/Thesis_Proposal.pdf` (chương 2.3 phương pháp, chương 4.2 lịch 6 tháng). Luận văn có hai câu hỏi: RQ1 vai trò của LLM, RQ2 bằng chứng tìm thấy (placebo + bài cài tín hiệu).

## Việc

| # | Việc | Trạng thái | Tới đâu | Chi tiết |
|---|---|---|---|---|
| 1 | Proposal luận văn | ✅ | 26 trang, mẫu IU, có chữ ký | `proposal/` |
| 2 | Lõi: backtest, toán tử `ts_*`, giả lập HMM | ✅ | kiểm trên dữ liệu thật | [ARCH](design/ARCH.md) |
| 3 | Nối pipeline `ts_*`, tách dữ liệu khỏi engine, quy đổi theo năm | ✅ 2026-10-28 | `main.py mcts` thật chưa chạy (cần `--retrain-hmm` một lần) | [ARCH](design/ARCH.md) |
| 4 | Bộ 20 blueprint đóng băng | ✅ 2026-10-29 | `results/blueprint_sets/20261029_212813/` | [WALK_FORWARD](design/WALK_FORWARD.md#bộ-blueprint), [RESULTS](RESULTS.md#bộ-blueprint) |
| 5 | Bài cài tín hiệu ở cách chia cửa sổ 1 (hệ thống sinh một lần) | ✅ 2026-10-30 | 10 seed mỗi mức; ngưỡng phát hiện IC 0.1 (p = 0.005); so vị thế đủ 30 lượt | [PLANTED_SIGNAL](design/PLANTED_SIGNAL.md), [RESULTS](RESULTS.md#bài-cài-tín-hiệu-hệ-thống-sinh-một-lần-bộ-blueprint-cũ) |
| 6 | Tăng tốc lượt chấm MCTS | ✅ 2026-10-30 | hai lượt: backtest ≈ 2,2×, rồi chỉ số + IC: 17,3 → 9,8 ms; kết quả giống hệt | [RESULTS](RESULTS.md#tốc-độ) |
| 7 | Walk-forward LLM + MCTS | 🔧 | code xong (`main.py walkforward placebo\|freeze\|real\|summary`); placebo đã chạy (việc 8) | [WALK_FORWARD](design/WALK_FORWARD.md) |
| 8 | Placebo walk-forward (RQ2, hệ thống sinh một lần) | ✅ 2026-10-31 | 19 × 7 = 133 lượt, 6 giờ 10 phút; Sharpe placebo 0.11 ± 0.51, lớn nhất 1.02 ⇒ lần thật cần > 1.02 cho p = 0.05 | [WALK_FORWARD](design/WALK_FORWARD.md#placebo) |
| 9 | Vòng phản hồi LLM + cấu hình so sánh (RQ1) + sửa prompt | ✅ 2026-10-31 | phần 1 `2ed3c49`, phần 2 `dee8ed8` (LLM không tìm, mua và giữ, TSMOM, Fisher + Holm, bootstrap Sharpe, đóng băng khoá mọi đầu vào); web RQ1 `07874f2`; 570 test qua | [LLM_FEEDBACK](design/LLM_FEEDBACK.md) |
| 9a | Sinh lại bộ blueprint bằng prompt đã sửa, đóng băng | ✅ 2026-10-31 | `results/blueprint_sets/20261031_rq1/`; 4 A chốt trước (DECISIONS) | [LLM_FEEDBACK](design/LLM_FEEDBACK.md#sửa-prompt) |
| 9b | Đo một lượt có phản hồi (thời gian LLM) | ✅ 2026-10-31 | LLM ≈ 110 s mỗi yêu cầu; cả kế hoạch ≈ 12–20 giờ, dưới ngưỡng dừng 48 giờ ⇒ giữ thiết kế | [LLM_FEEDBACK](design/LLM_FEEDBACK.md#thứ-tự-và-thời-gian-máy) |
| 9c | Bài cài tín hiệu RQ1: 3 cấu hình × 4 A × 3 IC × 10 seed | ✅ | xong 2026-11-02 12:35 (360 ô, `results/planted_rq1/`); kiểm định chính không có ý nghĩa (p Holm ≥ 0.94); số ở [RESULTS](RESULTS.md#bài-cài-tín-hiệu-rq1-hệ-thống-có-phản-hồi-bộ-rq1) | [LLM_FEEDBACK](design/LLM_FEEDBACK.md#bài-cài-tín-hiệu-cho-rq1) |
| 9d | Placebo chạy lại trên hệ thống có phản hồi | ✅ | xong 2026-11-02 14:11 (133 lượt, `results/walkforward/llm_mcts/`): Sharpe trung bình −0.15, lớn nhất 1.04 ⇒ p = 0.05 cần Sharpe thật > 1.04; số ở [RESULTS](RESULTS.md#placebo-walk-forward-hệ-thống-có-phản-hồi-bộ-rq1) | [WALK_FORWARD](design/WALK_FORWARD.md#placebo) |
| 9e | Sửa vòng phản hồi LLM | ✅ | `415227e` + `6719dc9`: ngữ cảnh 32k, chờ 6 giờ, công thức phản hồi bỏ cửa sổ, ghi lý do lỗi, chặn 16.384 token + thử lại 2 lần. Chạy thử lần 2: 0/10 lượt rơi về, 4/10 cần thử lại | [log](log/2026-11_LLM_FEEDBACK.md) |
| 10 | Đóng băng (`results/walkforward/frozen.json`) | ✅ | 2026-11-02, code ở `9d58d63`, commit `bfe7faf`: bộ blueprint `20261031_rq1` (sha `31e8c4c1…`), bộ 100 công thức LLM không tìm `results/formula_sets/20261102_llm_only/` (sinh 17:25 → 18:25), p placebo trên seed 1 | [WALK_FORWARD](design/WALK_FORWARD.md#đóng-băng) |
| 11 | Chạy thật một lần, chuỗi lợi suất ngoài mẫu 2022-07 → 2025-12 | ✅ 2026-11-02 | 6 cấu hình xong 22:12; LLM + MCTS Sharpe seed 1 = 0.68, p placebo = 0.15; mọi CI chênh với cấu hình khác chứa 0; LLM không tìm 1.10 ([RESULTS](RESULTS.md#walk-forward-thật-đóng-băng-bfe7faf)) | [WALK_FORWARD](design/WALK_FORWARD.md) |
| 12 | Đo lại ước thời gian walk-forward sau tăng tốc | 🔧 | placebo đo được 1.612 s/lượt (ước cũ 14 giờ ⇒ thật 6 giờ 10 phút với 10 lượt song song); các phần khác chưa ước lại | [WALK_FORWARD](design/WALK_FORWARD.md#thời-gian-máy) |
| 13 | SPA / DSR | ✅ 2026-11-03 | placebo thay SPA / DSR; DSR phụ cho 18 chuỗi thật: không chuỗi nào ≥ 0.95, LLM không tìm 0.65; luận văn có thể bỏ (câu hai bản ở WALK_FORWARD) | [WALK_FORWARD](design/WALK_FORWARD.md#dsr-phụ-tuỳ-chọn) |
| 14 | Web điều khiển và theo dõi | 🔧 | W1, W3b (web luận văn, 2026-10-30; trang placebo và ngưỡng Fisher 2026-10-31) xong; W2, W3–W6 còn | [WEB_DASHBOARD](design/WEB_DASHBOARD.md) |

## Câu chưa ai trả lời

- ⏸️ Gộp alpha: top-5 trọng số đều (proposal) hay thêm tổ hợp tuyến tính kiểu RiskMiner làm cấu hình phụ. Suy đoán của Claude: trọng số đều an toàn hơn vì ít dữ liệu.
- ⏸️ Placebo chính: hoán vị lợi suất (proposal, code đang dùng) hay đổi dấu theo ngày.
- ⏸️ Số seed 5 cho lần chạy thật: Claude đề xuất theo proposal, chưa xác nhận riêng. (K = 19 đang chạy; muốn K = 39 thì chạy thêm bộ 20–39 sau, không phải chạy lại.)
- ⏸️ Ngân sách placebo bằng lần thật nếu thời gian máy cho phép: Claude đề xuất.
- ⏸️ Ghi số lệnh và Sharpe sau phí của A như một dòng mô tả tín hiệu cài trong kết quả bài cài tín hiệu.

## Nợ

- `main.py walkforward summary` in p = 1.0 cho cấu hình không có placebo (nên là NaN); code đang đóng băng nên chưa sửa.
- Lần thật LLM + MCTS trung vị 509 lệnh mỗi cửa sổ, placebo 48: chưa giải thích.
- Viết lại các câu RQ1 sai sau review 2026-11-02 ([log](log/2026-11_LLM_FEEDBACK.md)): "A ngoài vùng" (chỉ đúng về cấu trúc, `sub(?, ?)` điền được A − hằng), "chia đoạn như cửa sổ 1" (thật ra là `Segments()` mặc định), "LLM tới A sớm hơn" (lần đầu chạm đo theo khối 500 vòng); báo tìm lại gần ở ngưỡng 0.7 / 0.8 / 0.9. Áp cho RESULTS, LLM_FEEDBACK, PLANTED_SIGNAL và chữ trên web.

- `criteria_report` của `main.py planted summary` vẫn in đạt / trượt theo tiêu chí cũ (IC 0.05 ≥ 3/5), trong khi bài này đã đổi sang báo ngưỡng phát hiện.
- ≈ 7% lượt chấm lỗi (−10) — người dùng chốt 2026-10-30 để nguyên, ghi vào mục hạn chế (như nhau ở mọi cấu hình; sửa thì phải chạy lại mọi kết quả) vì biểu thức toàn hằng (`Input array/series must be 1D, got shape ()`); MCTS còn sinh `(0.1 + low)`. Cần lọc hằng theo nút cha. Sau mỗi lượt xem `MCTSEngine.error_summary()`.
- `CRITICAL_RULES` (dùng chung mọi biến thể prompt) còn xếp `ts_argmax` / `ts_argmin` vào nhóm "giữ chiều"; không sửa vì đổi hash prompt `current`. Template vẫn chọn theo `output_dim` khai báo.
- Rò rỉ qua trọng số LLM: `qwen3.5:4b` có thể đã đọc văn bản về 2020–2025. Đã ẩn tên thị trường trong prompt; đã dò mức và hướng VN30 theo tháng 2020–2025 (2026-10-31: không hơn đoán hằng, [RESULTS](RESULTS.md#rò-rỉ-qua-trọng-số-llm)); ngày cắt không công bố. Còn: so blueprint có tên và ẩn danh cùng ngân sách, nêu trong mục hạn chế.
- Dữ liệu khung phút thiếu 126 ngày (2023-03-22 → 2024-03-14) so với tệp 1H; kiểm tệp gốc trước khi chạy RQ trên khung phút.
- Template BOOLEAN luôn có vị thế (bar NaN và False thành short); RATIO 60–80 / 20–40 làm gốc `ts_zscore` gần như luôn short.
- `generate_strategy_code` mới test với NORMALIZED; `generate_descriptive_name` còn tìm `self.feat.*`.
- `test_hardware_concurrency.py` gọi `run_mcts_pipeline` thật nên ghi thêm vào `results/mcts_stats.json` (thay đổi này không commit).
- `results/portfolio_summary.json`, `3tier_results.csv` tính theo công thức cũ, chỉ có chiến lược thế hệ đầu; `results/pushed/` khôi phục bằng `git checkout cfeb770 -- results/pushed`.
- Ảnh chữ ký và PDF đã ký trong `proposal/` chỉ nằm trên máy (`.gitignore`).
- Người dùng tự làm: báo thầy RQ2 cũ đã bỏ, câu hỏi đánh số lại và RQ1 đổi thước đo sang ngưỡng phát hiện; đăng xuất mọi phiên DeepSeek và Google (token cũ có thể còn hiệu lực).
