# Lưu trữ — tài liệu không còn đúng với code

Các tệp ở đây là **lịch sử**, giữ lại để tra cứu, ⛔ không dùng làm căn cứ cho kiến trúc hay kế hoạch hiện tại.
Kiến trúc hiện tại: `docs/ARCH.md`. Kế hoạch hiện hành: `docs/ROADMAP.md`.

| Tệp | Nội dung | Vì sao lưu trữ |
|---|---|---|
| `build_alpha_exp.md` | Kinh nghiệm thử các chiến lược viết tay (Alpha 101, Basis Arbitrage, ORB, Heikin-Ashi) trên sandbox XNOQuant | Thuộc thời XNOQuant; số liệu đo trên sandbox web và backtest cũ |
| `experience_log.md` | "Bài học" bằng tiếng Anh để nhét vào prompt LLM (tránh chia cho Volume = 0, luật AST của XNOQuant) | Luật XNOQuant không còn áp dụng; code đọc `utilities/experience_log.md` (tệp này không tồn tại), không đọc bản ở đây |
| `feature.txt`, `operator.txt` | Danh sách hàm `self.feat.*` (TA-Lib) và `self.op.*` của SDK XNOQuant | `FeatureEngine` / `OperatorEngine` đã bị gỡ ở commit `3bdc8fd` |
| `feature_op_expansion.md` | Phân loại hàng trăm hàm TA-Lib theo thứ nguyên để đưa vào MCTS | Không gian tìm kiếm nay chỉ gồm toán tử `ts_*`, logic và số học |
| `prompt_update.md` | Nhận xét về prompt sinh blueprint thời TA-Lib | Prompt hiện tại vẫn là bản TA-Lib và đang lỗi (xem ROADMAP); khi sửa sẽ viết lại, không theo tệp này |
| `plan.md` | Lý do thiết kế kiến trúc 3 tầng (LLM → trình biên dịch → MCTS) và bài báo gốc của từng ý | Phần còn đúng đã đưa vào `ARCH.md` mục "Nguồn gốc ý tưởng"; có trích Chain-of-Alpha, bài này đã bị tác giả rút khỏi arXiv |
| `HMM_MonteCarlo_Validation.md`, `HMM_MonteCarlo_Results.csv` | Kết quả lọc 149 alpha thế hệ đầu bằng bộ luật HMM cũ (Rule 1–4, theo phân vị Sharpe) | Bộ luật này đã được thay bằng kiểm định 3 tầng; các alpha là bản TA-Lib |
| `proposal_vi_draft/` | Bản proposal tiếng Việt viết trước khi có mẫu của khoa | Thay bằng `docs/proposal/thesis_proposal/` |
