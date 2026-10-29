# Kế hoạch hiện hành — Alpha Farm (luận văn)

Bản hiện hành. Đổi ý thì sửa đúng chỗ, kèm một dòng lý do + ngày.
Khung nghiên cứu: `docs/proposal/thesis_proposal/Thesis_Proposal.pdf` (chương 2.3 là phương pháp sẽ làm, chương 4.2 là lịch 6 tháng).

## 1. Hiện trạng (2026-10-13)

- ✅ Proposal đã viết xong theo mẫu IU, 26 trang, có chữ ký.
- ✅ Lõi dùng được, đã kiểm chứng trên dữ liệu thật:
  - Backtest VN30F không nhìn trước tương lai (tín hiệu bar t khớp ở bar t+1).
  - 9 toán tử `ts_*` không nhìn trước tương lai, khớp pandas.
  - Bộ giả lập HMM sát thực tế (độ dài chế độ 0.72–0.92 lần, MDD tương đương).
- ✅ Pipeline `ts_*` chạy hết từ blueprint tới code chiến lược xuất ra (2026-10-28, việc 1 ở mục 2).
- ⛔ Chưa có thành phần nào của quy trình đánh giá mới (walk-forward, gộp top-k, seed, baseline, placebo, cài tín hiệu, SPA/DSR).
- ✅ Quy đổi theo năm thống nhất, CAGR theo lịch (2026-10-28, việc 4).
- ⛔ Test: `.venv` cho 183 pass, 1 fail (`test_core_engine.py::test_alpha_data_proxy`, có từ trước) — đo 2026-10-29.

- ✅ Dọn tài liệu (2026-10-13): `docs/ARCH.md` và `README.md` viết lại theo code; bài báo vào `docs/references/`; tài liệu thời XNOQuant vào `docs/archive/` (lý do từng tệp ở `docs/archive/README.md`).

## 2. Việc theo thứ tự (Tháng 1 của proposal)

1. ✅ **Nối lại pipeline** (2026-10-28): sửa 4 chỗ nối ở mục 1, đặt seed cho MCTS, cửa sổ cố định trên từng nút. Đo thật: 60m, `sub(ts_mean(?), ts_mean(?))`, seed 1, 300 vòng → 4 ứng viên reward ≠ −10, tốt nhất 0.26; cùng seed cho cùng kết quả kể cả khác tiến trình. Test: `tests/test_mcts_pipeline.py` (12 ca). `main.py mcts` thật (cần cache HMM) chưa chạy.
2. ✅ **Tách dữ liệu khỏi engine** (2026-10-28): `MCTSEngine`, HMM và `process_timeframe` nhận DataFrame từ ngoài; cache HMM khoá theo khung + dấu vân tay dữ liệu. Test: `tests/test_data_injection.py` với `load_data` bị chặn. Cache cũ 13 GB không còn được đọc: chạy `--retrain-hmm` một lần trước lượt `mcts` thật.
3. ⏸️ **Bài cài tín hiệu (kiểm soát dương), một khung thời gian** — thiết kế: `docs/PLANTED_SIGNAL.md`, người dùng duyệt 2026-10-28. Lần 2 (mục 9): IC 0.05 trượt (gần 1/5), IC 0 đạt, ngưỡng phát hiện ≈ IC 0.1. Lần 3 (mục 10: dữ liệu 2018-08 → 2024-12, reward `sharpe`): IC 0.05 vẫn 1/5, IC 0.1 lên 5/5, IC 0 đạt; ngưỡng nằm giữa 0.05 và 0.1. Tách tác động: phần cải thiện chủ yếu do dữ liệu. Đã đủ để chốt (mục 3, 2026-10-29); dùng lại bài này để đo độ nhạy ở cách chia của cửa sổ walk-forward đầu tiên. Mục tiêu gốc: cài một công thức biết trước vào lợi suất placebo với IC 0.01 / 0.02 / 0.05, xem MCTS có tìm lại được không. Xong khi: có bảng tỷ lệ tìm lại theo cường độ.
4. ✅ Sửa quy đổi theo năm (2026-10-28): mọi chỉ số đi qua `compute_metrics`; CAGR theo thời gian lịch. Đo thật CAGR mua-và-giữ 2020–2024: 8.94% (1m), 8.93% (15m), 8.90% (60m) — trước đây 0.76% / 20.0% trong HMM và 10.1% trong `compute_metrics` khung phút (do thiếu ngày). Kết quả cũ trong `results/` (`portfolio_summary.json`…) vẫn tính theo công thức cũ.

5. ⏸️ **Web điều khiển và theo dõi** (người dùng yêu cầu 2026-10-28; ngoài lịch proposal; mở từ xa qua Tailscale, người dùng chốt 2026-10-28) — kế hoạch: `docs/WEB_DASHBOARD.md`. ✅ W1 (móc tiến độ, dừng, danh sách blueprint, đếm −10 theo lý do) xong 2026-10-28; ✅ W3a (web chỉ xem bài cài tín hiệu + tài nguyên máy, `main.py web`) xong 2026-10-29 — người dùng cho làm sớm vì khó hình dung kết quả qua chat; W2, W3–W6 còn lại.

6. 🔧 **Walk-forward (Tháng 2)** — thiết kế: `docs/WALK_FORWARD.md` (đang viết, chờ người dùng duyệt trước khi code).

Tháng 2 trở đi theo bảng 4.1 của proposal: walk-forward + gộp top-k + placebo + baseline → chạy RQ1 → RQ2, SPA, DSR (RQ2 cũ đã bỏ, RQ3 cũ thành RQ2; mục 3).

## 3. Câu chưa ai trả lời (⏸️ chờ người quyết)

- ⏸️ Gộp alpha: trung bình vị thế top-5 trọng số đều (đang ghi trong proposal) hay thêm tổ hợp tuyến tính kiểu RiskMiner làm cấu hình phụ. Suy đoán của Claude: trọng số đều an toàn hơn vì ít dữ liệu; chưa ai chốt.
- ⏸️ Cách tạo placebo chính: hoán vị lợi suất (theo Masters/Aronson) hay đổi dấu theo ngày. Proposal ghi hoán vị là chính.
- ✅ Tệp nháp (`docs/log.txt`, `PROJECT.md`, `ORIGINAL_REQUEST.md`, `.agents/`): người dùng chọn chuyển vào `docs/archive/` (2026-10-13).
- ✅ Chỉ dùng LLM chạy máy (Ollama); gỡ code DeepSeek / Gemini, bỏ `token.txt`, `cookies.txt`, `api.txt` (người dùng chốt 2026-10-28). Proposal không nêu tên nhà cung cấp LLM nên không phải sửa; luận văn phải ghi rõ mô hình local đã dùng.
- ✅ Vai trò bộ lọc HMM: proposal mục "Statistical Tests" đã chốt — HMM không nằm trong vòng chọn, chỉ mô tả rủi ro của chiến lược đã qua các test khác (2026-10-28, đối chiếu proposal). Vì vậy bootstrap từ toàn giai đoạn không làm rò rỉ vào kết quả; lỗi khoá cache theo khung vẫn sửa trong việc 2.
- ✅ Các cổng cứng (người dùng chốt 2026-10-28 theo đề xuất của Claude):
  - Cổng reward (−10 nếu < 15 lệnh hoặc Calmar < 1.1): có hai bản reward. Bản "gated" (như cũ) và bản "soft" (bỏ ngưỡng Calmar; dưới 15 lệnh thì phần Calmar bằng 0, phần IC vẫn giữ; chỉ lỗi mới −10). Chọn bản bằng bước chấm đáp án của việc 3 (`docs/PLANTED_SIGNAL.md` mục 5), rồi đóng băng trước walk-forward trên dữ liệu thật.
  - HMM: chỉ ghi kết quả, không loại chiến lược (khớp proposal).
  - Tiêu chí danh mục (`meets_criteria`, `force_add`, loại theo tương quan) và phạt −100 FSA: xoá, vì là code chết (FSA chỉ kích khi reward > 1.0, mà reward tối đa là 1.0).
  - Lọc `reward > 0` trước khi chọn: giữ tới khi làm gộp top-5.
- ✅ Bài cài tín hiệu lần 1 trượt ở IC 0.05 (`docs/PLANTED_SIGNAL.md` mục 8): công thức nhiễu tốt nhất luôn thắng tín hiệu thật trong mẫu. Người dùng chốt làm cả ba (2026-10-28): (a) sửa lỗi top-5 trùng công thức; (b) chọn top-5 trên một đoạn kiểm định tách riêng trong đoạn tìm (ví dụ 6 tháng cuối) thay vì reward trong mẫu; (c) thêm độ mạnh IC 0.1 / 0.2 để tìm ngưỡng phát hiện.
- ✅ **Sau bài cài tín hiệu (người dùng chốt 2026-10-29 theo đề xuất của Claude):**
  - Báo cáo bài cài tín hiệu theo **ngưỡng phát hiện** ứng với lượng dữ liệu (≈ IC 0.1 với ~2 năm; giữa 0.05 và 0.1 với ~5 năm), không theo đạt / trượt ở IC 0.05. Proposal chỉ ghi các mức IC "for example", không có tiêu chí đạt.
  - **Reward đóng băng: `sharpe`** (`docs/PLANTED_SIGNAL.md` mục 10). Lý do: không lệch theo độ dài dữ liệu như Calmar, khớp thước đo chính của proposal, không báo nhầm trên placebo với dữ liệu dài.
  - **Walk-forward đổi so với proposal:** cửa sổ nở dần từ 2018-08-13 (mỗi cửa sổ dùng toàn bộ dữ liệu trước nó), đoạn tìm ngắn nhất ≈ 4 năm, đánh giá 6 tháng lăn 6 tháng, 7 cửa sổ đánh giá 2022-07 → 2025-12 (dùng cả 2025, đúng như proposal). Lý do: 2 năm tìm chỉ phát hiện được IC ≥ 0.1. Đánh đổi: 3,5 năm ngoài mẫu thay vì 5,5 ⇒ Sharpe tối thiểu chứng minh được ≈ 1.07 thay vì 0.85. Người dùng: proposal là bản "sẽ làm gì" cho thầy xem, đổi được.
  - **Bỏ RQ2 cũ** (toán tử cơ bản vs chỉ báo kỹ thuật; người dùng chốt 2026-10-29, Claude đồng ý). Lý do: không trả lời câu hỏi chính (hệ thống có tìm ra tín hiệu thật không); chỉ báo kỹ thuật vốn là tổ hợp toán tử cơ bản nên so sánh chỉ đo độ thô của ngữ pháp; với ngưỡng phát hiện ≈ IC 0.1 kết quả gần chắc "không phân biệt được"; chi phí lớn nhất (dựng lại toán tử chỉ báo sau khi gỡ TA-Lib). Độ nhạy theo lượng dữ liệu báo trong RQ2 mới (bài cài tín hiệu), không thành câu riêng. Luận văn ghi câu này vào hướng phát triển; cần báo thầy vì proposal có RQ2.
  - ✅ **Đánh số lại** (người dùng chốt 2026-10-29): RQ3 cũ (bằng chứng tìm thấy: placebo + bài cài tín hiệu) thành **RQ2**. Luận văn còn hai câu: RQ1 vai trò của LLM, RQ2 bằng chứng tìm thấy. Proposal giữ nguyên số cũ.
  - **Quy tắc dữ liệu thật:** mọi lựa chọn (reward, cách chia đoạn, bộ blueprint, ngân sách, seed) ghi vào tài liệu và đóng băng **trước** lần chạy walk-forward đầu tiên trên dữ liệu thật; chạy một lần, không sửa theo kết quả. Mọi lần chỉnh tới nay chỉ chạy trên dữ liệu đã xáo.
- ⏸️ Số seed (5), K = 19 lần placebo: do Claude đề xuất (theo proposal), người dùng chưa xác nhận riêng.

## 4. Nợ

- Bài cài tín hiệu lần 1–3 chạy trên ngữ pháp cũ (chiều không lan qua `ts_*`, `?` điền sai chiều được). Kết quả ở `docs/PLANTED_SIGNAL.md` là của không gian tìm cũ, rộng hơn; lần chạy cách chia cửa sổ 1 (đã định, `docs/WALK_FORWARD.md` mục 2) chạy trên ngữ pháp mới và là số luận văn dùng. Ghi 2026-10-29.
- `CRITICAL_RULES` (dùng chung mọi biến thể prompt) còn xếp `ts_argmax` / `ts_argmin` vào nhóm "giữ chiều"; không sửa vì đổi hash prompt `current`. Không ảnh hưởng template (template vẫn chọn theo `output_dim` khai báo).

- ⛔ Token DeepSeek từng bị đẩy lên GitHub (lịch sử git đã viết lại, tệp đã xoá khỏi máy 2026-10-28) nhưng token và cookie Gemini có thể vẫn còn hiệu lực: người dùng tự đăng xuất mọi phiên ở chat.deepseek.com và Google.
- Rò rỉ qua trọng số LLM (nêu 2026-10-28, người dùng cho vào nợ): `qwen3.5:4b` được huấn luyện trên văn bản có thể đã nói về 2020–2025, nên lợi ích của LLM ở RQ1 có thể lẫn "biết trước". Prompt ghi tên "VN30 Index Futures" nhưng không ghi ngày. Cách kiểm Claude đề xuất: (1) ẩn tên thị trường trong prompt; (2) so blueprint có tên và ẩn danh cùng ngân sách; (3) tra ngày cắt dữ liệu huấn luyện của qwen3.5, tách cửa sổ đánh giá sau ngày đó; (4) nêu trong mục hạn chế. Chưa đo.
- ⛔ Dữ liệu thiếu ngày (đo 2026-10-28): giai đoạn 2020–2024, tệp 1m/5m/15m/30m có 1.121 ngày giao dịch, tệp 1H có 1.247; 126 ngày chỉ có ở 1H, rải từ 2023-03-22 tới 2024-03-14. Backtest khung phút nhảy qua các ngày đó như một bar. Cần kiểm tệp CSV gốc / tải lại trước khi chạy RQ trên khung phút.
- Test `test_hardware_concurrency.py` gọi `run_mcts_pipeline` thật nên mỗi lần chạy test ghi thêm vào `results/mcts_stats.json`.
- `results/pushed/` (chiến lược thế hệ đầu) bị xoá ở commit `c6b1f03`; khôi phục bằng `git checkout cfeb770 -- results/pushed` nếu cần (RQ2 cũ về chỉ báo kỹ thuật đã bỏ nên không còn dùng để so sánh).
- ~~`GenerateStrategies.load_experience_log` đọc tệp không tồn tại~~ → ✅ báo rõ khi thiếu, prompt ghi "(No experience log is available.)" (2026-10-28).
- Không gian tìm phí: 12% lượt chấm lỗi vì biểu thức toàn hằng (`ts_mean((0.2 + 0.5), 10)`); MCTS còn sinh `(0.1 + low)` — cộng hằng vào giá không đổi z-score. Cần lọc hằng theo nút cha.
- Template BOOLEAN luôn có vị thế: bar NaN lúc khởi động (và mọi bar False) thành vị thế short. Template RATIO với ngưỡng 60–80 / 20–40 làm gốc `ts_zscore` gần như luôn short; prompt đang bảo LLM tránh gốc RATIO.
- `generate_strategy_code` mới được test với template NORMALIZED; RATIO / BOOLEAN dựa vào việc dùng chung `compute_positions`.
- ✅ Môi trường (2026-10-28): thêm `requirements.in` / `requirements.txt`, `.venv` sync theo đó (66 → 35 gói, 537 → 321 MB; bỏ playwright, google-generativeai, openai, ta-lib, psutil, pytest-mock; thêm matplotlib 3.11.2). Test vẫn 49 pass / 1 fail; `make_figures.py` chạy được bằng `.venv`. Hình `walk_forward.png` vẽ lại khác byte với bản trong PDF nên giữ bản cũ.
- `generate_descriptive_name` còn tìm `self.feat.*` nên tên chiến lược luôn rơi về tên trường.
- `results/mcts_stats.json` có thay đổi chưa commit (do lượt chạy MCTS cũ và các lượt chạy test ghi thêm).
- Ảnh chữ ký và PDF đã ký trong `docs/proposal/` chỉ nằm trên máy (`.gitignore`), không có trong git; mất máy là mất.
