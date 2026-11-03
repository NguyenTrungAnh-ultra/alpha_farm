# Bảng kiểm luận văn theo hướng dẫn BM Toán

Mỗi yêu cầu của [hướng dẫn LVTN 2026-27](THESIS_GUIDE.md) một dòng: hạn, trạng thái, bằng chứng. Web `/guide` đọc bảng dưới để vẽ timeline và danh sách kiểm. Giữ đúng 5 cột; cột Hạn ghi `YYYY-MM-DD`, khoảng `YYYY-MM-DD → YYYY-MM-DD` hoặc `—`. Trạng thái: ✅ xong · 🔧 đang làm · ⏸️ chờ người dùng xác nhận · ⛔ bị chặn / rủi ro · `chưa`.

## Mốc của khoa

| Việc | Nhóm | Hạn | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|---|---|
| Đủ 118 tín chỉ để làm LVTN | Điều kiện | — | ⏸️ | người dùng tự kiểm trên cổng đào tạo |
| Buổi hướng dẫn online (GV Nguyễn Minh Quân) | Mốc khoa | 2026-09-27 | ⏸️ | |
| Tên đề tài trên Google Sheet khớp từng chữ với form đã ký | Mốc khoa | 2026-10-09 | ⏸️ | tên trong proposal: "LLM-Guided, Dimension-Constrained Monte Carlo Tree Search for Formulaic Alpha Discovery in VN30F Index Futures"; so với tab "Đăng kí đề tài HK1 26-27" |
| Email form xác nhận đề tài có chữ ký điện tử GVHD, cc GVHD | Mốc khoa | 2026-10-09 | ⏸️ | |
| Proposal có chữ ký điện tử SV và GVHD | Mốc khoa | 2026-10-09 | ✅ | `proposal/thesis_proposal/Thesis_Proposal_NguyeenXTrungAnh_MAMAIU22123.pdf` |
| Gửi proposal qua ma@hcmiu.edu.vn, cc GVHD | Mốc khoa | 2026-10-09 | ⏸️ | |
| BM duyệt proposal (không nhận góp ý sau 14/10 = được duyệt) | Mốc khoa | 2026-10-14 | ⏸️ | |
| Thực hiện luận văn (14 tuần) | Mốc khoa | 2026-10-14 → 2027-01-20 | 🔧 | bản nháp đủ chương 2026-11-03 |
| Nộp file thesis có chữ ký điện tử SV và GVHD qua ma@hcmiu.edu.vn | Mốc khoa | 2027-01-20 | chưa | |
| Nộp bản giấy | Mốc khoa | 2027-01-21 | chưa | hướng dẫn ghi "trước 22/01/2027" |
| Bảo vệ luận văn (thuyết trình ≤ 15 phút) | Mốc khoa | 2027-02-17 → 2027-02-23 | chưa | |
| Nộp bản cứng bìa mạ vàng và cam kết cho thư viện | Mốc khoa | 2027-03-14 | chưa | mẫu "Format Gold version", "Thesis Submission Commitment" |

## Nghiên cứu

| Việc | Nhóm | Hạn | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|---|---|
| Bài cài tín hiệu cửa sổ 1 (hệ thống sinh một lần) | Nghiên cứu | 2026-10-30 | ✅ | [RESULTS](RESULTS.md) |
| Bài cài tín hiệu RQ1 (360 ô) | Nghiên cứu | 2026-11-02 | ✅ | `results/planted_rq1/` |
| Placebo walk-forward (19 bộ) | Nghiên cứu | 2026-11-02 | ✅ | `results/walkforward/llm_mcts/` |
| Đóng băng cấu hình, chạy thật một lần | Nghiên cứu | 2026-11-02 | ✅ | `results/walkforward/frozen.json`, commit `bfe7faf` |
| DSR (phụ) | Nghiên cứu | 2026-11-03 | ✅ | `results/walkforward/dsr.csv` |
| Bản nháp luận văn đủ chương | Nghiên cứu | 2026-11-03 | ✅ | `thesis/Thesis.pdf`, `thesis/Thesis_noDSR.pdf` |

## Nội dung luận văn

| Việc | Nhóm | Hạn | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|---|---|
| Viết bằng LaTeX theo mẫu `Sample_Thesis_Tex_format_2026` | Nội dung | — | ✅ | `thesis/Thesis.tex` |
| Abstract một trang | Nội dung | — | ✅ | trang 3 của PDF |
| Acknowledgement một trang | Nội dung | — | ✅ | mới 2 câu; người dùng viết thêm nếu muốn |
| Introduction: bối cảnh, vấn đề, mục đích, kết quả kỳ vọng, cấu trúc luận văn | Nội dung | — | ✅ | chương 1, mục 1.1–1.5 |
| Literature review là chương riêng, nêu gap dẫn tới đề tài | Nội dung | — | ✅ | chương 2, mục 2.5 |
| Nền tảng toán / background | Nội dung | — | 🔧 | gộp vào chương 3 (hướng dẫn cho phép); công thức UCT, sai số chuẩn Sharpe, phép Fisher, stationary bootstrap chưa viết tường minh |
| Methodology | Nội dung | — | ✅ | chương 3 |
| Results: dữ liệu, cách vận hành model, kết quả, quan sát | Nội dung | — | ✅ | chương 4 |
| Discussion and conclusion, có hạn chế | Nội dung | — | ✅ | chương 5–6 |
| References chỉ gồm tài liệu có trích dẫn | Nội dung | — | ✅ | kiểm 2026-11-03: 0 mục thừa, 0 mục thiếu |
| Appendix có mã QR dẫn tới code | Nội dung | — | ✅ | phụ lục A |
| Ngày trên bìa đúng tháng nộp | Nội dung | 2027-01-20 | chưa | đang ghi tạm "November 2026" (`\thesisdate`) |

## Trước khi nộp

Hạn ở mục này và mục Bảo vệ là đề xuất của Claude (2026-11-03), người dùng chưa chốt; hạn của khoa nằm ở mục đầu.

| Việc | Nhóm | Hạn | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|---|---|
| Người dùng đọc lại, viết lại bằng lời của mình | Trước khi nộp | 2026-12-15 | chưa | bản nháp do Claude soạn |
| GVHD đọc và góp ý bản thảo | Trước khi nộp | 2026-12-31 | chưa | báo thầy: RQ đổi so với proposal (chương 3, mục 3.9) |
| Kiểm chính tả tiếng Anh (Grammarly) | Trước khi nộp | 2027-01-10 | chưa | |
| Turnitin: trùng lặp < 20 % (BM khuyến nghị ≤ 15 %) | Trước khi nộp | 2027-01-15 | chưa | |
| Turnitin: AI writing < 20 % (BM khuyến nghị ≤ 15 %) | Trước khi nộp | 2027-01-15 | ⛔ | rủi ro cao: văn bản hiện do AI soạn; phải tự viết lại trước khi kiểm |
| Chữ ký điện tử SV và GVHD trên bản nộp | Trước khi nộp | 2027-01-20 | chưa | |
| Slide bảo vệ (mẫu slide LaTeX của khoa) | Bảo vệ | 2027-02-10 | chưa | |
| Tập thuyết trình ≤ 15 phút và trả lời câu hỏi | Bảo vệ | 2027-02-16 | chưa | tiêu chí 7: 15 điểm |
