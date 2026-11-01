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
| 9c | Bài cài tín hiệu RQ1: 3 cấu hình × 4 A × 3 IC × 10 seed | 🔧 | ô MCTS không LLM / tìm ngẫu nhiên đang chạy ở `results/planted_rq1/` (log `results/logs/rq1_search.log`); 90 ô LLM + MCTS chạy lại từ 2026-11-01 22:00 ở `results/planted_rq1_llm/` (log `results/logs/rq1_llm_rerun.log`), xong thì thay 90 dòng hỏng | [LLM_FEEDBACK](design/LLM_FEEDBACK.md#bài-cài-tín-hiệu-cho-rq1) |
| 9d | Placebo chạy lại trên hệ thống có phản hồi | 🔧 | chạy lại từ 2026-11-01 22:00 (133 lượt, 6 worker, log `results/logs/placebo_llm_mcts_rerun.log`, ước ≈ 14 giờ cùng 9c); bản hỏng ở `results/walkforward/llm_mcts_broken_20261101/`; kết quả việc 8 (hệ thống sinh một lần) ở `results/walkforward/oneshot_placebo/` | [WALK_FORWARD](design/WALK_FORWARD.md#placebo) |
| 9e | Sửa vòng phản hồi LLM | ✅ | `415227e` + `6719dc9`: ngữ cảnh 32k, chờ 6 giờ, công thức phản hồi bỏ cửa sổ, ghi lý do lỗi, chặn 16.384 token + thử lại 2 lần. Chạy thử lần 2: 0/10 lượt rơi về, 4/10 cần thử lại | [log](log/2026-11_LLM_FEEDBACK.md) |
| 10 | Đóng băng (`results/walkforward/frozen.json`) | ⏸️ | làm sau việc 9–9d (đóng băng khoá code) | [WALK_FORWARD](design/WALK_FORWARD.md#đóng-băng) |
| 11 | Chạy thật một lần, chuỗi lợi suất ngoài mẫu 2022-07 → 2025-12 | ⏸️ | sau việc 10 | [WALK_FORWARD](design/WALK_FORWARD.md) |
| 12 | Đo lại ước thời gian walk-forward sau tăng tốc | 🔧 | placebo đo được 1.612 s/lượt (ước cũ 14 giờ ⇒ thật 6 giờ 10 phút với 10 lượt song song); các phần khác chưa ước lại | [WALK_FORWARD](design/WALK_FORWARD.md#thời-gian-máy) |
| 13 | SPA / DSR | chưa | Tháng 4 của proposal | |
| 14 | Web điều khiển và theo dõi | 🔧 | W1, W3b (web luận văn, 2026-10-30; trang placebo và ngưỡng Fisher 2026-10-31) xong; W2, W3–W6 còn | [WEB_DASHBOARD](design/WEB_DASHBOARD.md) |

## Câu chưa ai trả lời

- ⏸️ Gộp alpha: top-5 trọng số đều (proposal) hay thêm tổ hợp tuyến tính kiểu RiskMiner làm cấu hình phụ. Suy đoán của Claude: trọng số đều an toàn hơn vì ít dữ liệu.
- ⏸️ Placebo chính: hoán vị lợi suất (proposal, code đang dùng) hay đổi dấu theo ngày.
- ⏸️ Số seed 5 cho lần chạy thật: Claude đề xuất theo proposal, chưa xác nhận riêng. (K = 19 đang chạy; muốn K = 39 thì chạy thêm bộ 20–39 sau, không phải chạy lại.)
- ⏸️ Ngân sách placebo bằng lần thật nếu thời gian máy cho phép: Claude đề xuất.
- ⏸️ Ghi số lệnh và Sharpe sau phí của A như một dòng mô tả tín hiệu cài trong kết quả bài cài tín hiệu.

## Nợ


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
