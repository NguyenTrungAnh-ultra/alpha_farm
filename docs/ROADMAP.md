# Kế hoạch hiện hành — Alpha Farm (luận văn)

Bản hiện hành. Đổi ý thì sửa đúng chỗ, kèm một dòng lý do + ngày.
Khung nghiên cứu: `docs/proposal/thesis_proposal/Thesis_Proposal.pdf` (chương 2.3 là phương pháp sẽ làm, chương 4.2 là lịch 6 tháng).

## 1. Hiện trạng (2026-10-13)

- ✅ Proposal đã viết xong theo mẫu IU, 26 trang, có chữ ký.
- ✅ Lõi dùng được, đã kiểm chứng trên dữ liệu thật:
  - Backtest VN30F không nhìn trước tương lai (tín hiệu bar t khớp ở bar t+1).
  - 9 toán tử `ts_*` không nhìn trước tương lai, khớp pandas.
  - Bộ giả lập HMM sát thực tế (độ dài chế độ 0.72–0.92 lần, MDD tương đương).
- ⛔ Pipeline kiến trúc mới (toán tử `ts_*`) chưa chạy hết, đứt ở 4 chỗ nối (chi tiết trong `CLAUDE.md` mục "Known state"):
  1. `utilities/Prompts.py` vẫn dạy toán tử TA-Lib.
  2. `get_terminals_for_dimension` gọi `OperatorGroup.CANDLESTICK` đã xoá.
  3. `evaluate_expression` truyền `np.ndarray` vào backtest, lỗi `.shift` bị nuốt, mọi ứng viên nhận −10.
  4. Code chiến lược xuất ra dùng `self.feat` / `self.op` và không import `ts_*`.
- ⛔ Chưa có thành phần nào của quy trình đánh giá mới (walk-forward, gộp top-k, seed, baseline, placebo, cài tín hiệu, SPA/DSR).
- ⛔ Lỗi quy đổi theo năm trong `HMMValidation.calculate_metrics_for_result` (đã đo: CAGR mua-và-giữ 0.76% ở 1m, 20.0% ở 30m, đúng là 8.9%).
- ⛔ Test: `.venv` cho 37 pass, 1 fail (`test_core_engine.py::test_alpha_data_proxy`). Test hiện tại không chạm các đường hỏng ở trên.

- ✅ Dọn tài liệu (2026-10-13): `docs/ARCH.md` và `README.md` viết lại theo code; bài báo vào `docs/references/`; tài liệu thời XNOQuant vào `docs/archive/` (lý do từng tệp ở `docs/archive/README.md`).

## 2. Việc theo thứ tự (Tháng 1 của proposal)

1. ⏸️ **Nối lại pipeline**: sửa 4 chỗ nối ở mục 1, đặt seed cho MCTS, `ast_to_code` không chọn cửa sổ ngẫu nhiên lúc render. Xong khi: một blueprint dùng `ts_*` chạy hết MCTS và cho ra ứng viên có reward khác −10, có test chạy thật đường này.
2. ⏸️ **Tách dữ liệu khỏi engine**: `MCTSEngine` và `HMMValidation` nhận DataFrame từ ngoài thay vì tự gọi `load_data`. Xong khi: chạy được MCTS trên một DataFrame tuỳ ý (cửa sổ con, dữ liệu tổng hợp).
3. ⏸️ **Bài cài tín hiệu (kiểm soát dương), một khung thời gian**: cài một công thức biết trước vào lợi suất placebo với IC 0.01 / 0.02 / 0.05, xem MCTS có tìm lại được không. Xong khi: có bảng tỷ lệ tìm lại theo cường độ.
4. ⏸️ Sửa quy đổi theo năm trong `HMMValidation`.

Tháng 2 trở đi theo bảng 4.1 của proposal: walk-forward + gộp top-k + placebo + baseline → chạy RQ1/RQ2 → RQ3, SPA, DSR.

## 3. Câu chưa ai trả lời (⏸️ chờ người quyết)

- ⏸️ Gộp alpha: trung bình vị thế top-5 trọng số đều (đang ghi trong proposal) hay thêm tổ hợp tuyến tính kiểu RiskMiner làm cấu hình phụ. Suy đoán của Claude: trọng số đều an toàn hơn vì ít dữ liệu; chưa ai chốt.
- ⏸️ Cách tạo placebo chính: hoán vị lợi suất (theo Masters/Aronson) hay đổi dấu theo ngày. Proposal ghi hoán vị là chính.
- ✅ Tệp nháp (`docs/log.txt`, `PROJECT.md`, `ORIGINAL_REQUEST.md`, `.agents/`): người dùng chọn chuyển vào `docs/archive/` (2026-10-13).
- ⏸️ Độ dài cửa sổ walk-forward (2 năm tìm / 6 tháng đánh giá) và số seed (5), K = 19 lần placebo: do Claude đề xuất, người dùng chưa xác nhận.

## 4. Nợ

- ⛔ `token.txt` (token DeepSeek) nằm trong lịch sử git đã đẩy lên GitHub; link repo có trong proposal. Cần thu hồi token.
- `results/pushed/` (chiến lược thế hệ đầu) bị xoá ở commit `c6b1f03`; khôi phục bằng `git checkout cfeb770 -- results/pushed` nếu cần so sánh RQ2.
- `GenerateStrategies.load_experience_log` đọc `utilities/experience_log.md` — tệp không tồn tại nên prompt LLM nhận phần "kinh nghiệm" rỗng. Xử lý cùng lúc sửa prompt (việc 1).
- `results/mcts_stats.json` có thay đổi chưa commit (do lượt chạy MCTS cũ ghi thêm).
- Ảnh chữ ký và PDF đã ký trong `docs/proposal/` chỉ nằm trên máy (`.gitignore`), không có trong git; mất máy là mất.
