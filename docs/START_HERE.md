# Bắt đầu từ đây

Tệp cổng của vault `docs/` (mở thư mục này bằng Obsidian, hoặc đọc thẳng trên GitHub). Cần gì thì mở tệp nào:

| Cần | Mở |
|---|---|
| Việc gì đang làm, xong tới đâu, nợ, câu chưa ai trả lời | [PLAN](PLAN.md) |
| Đã quyết những gì, ai chốt, ngày nào | [DECISIONS](DECISIONS.md) |
| Con số luận văn đang dùng | [RESULTS](RESULTS.md) |
| Hệ thống chạy thế nào (đúng như code hôm nay) | [design/ARCH](design/ARCH.md) |
| Phương pháp bài cài tín hiệu (RQ2, độ nhạy) | [design/PLANTED_SIGNAL](design/PLANTED_SIGNAL.md) |
| Phương pháp walk-forward, cấu hình so sánh, placebo, đóng băng | [design/WALK_FORWARD](design/WALK_FORWARD.md) |
| Web điều khiển và theo dõi | [design/WEB_DASHBOARD](design/WEB_DASHBOARD.md) |
| Vòng phản hồi LLM, cấu hình so sánh và bài cài tín hiệu cho RQ1 | [design/LLM_FEEDBACK](design/LLM_FEEDBACK.md) |
| Công trình liên quan (LLM trong đầu tư, tìm alpha) | [design/RELATED_WORK](design/RELATED_WORK.md) |
| Vì sao ngày đó quyết thế, các lần chạy cũ, kết luận đã rút lại | [log/](log/) |
| Proposal luận văn | `proposal/thesis_proposal/Thesis_Proposal.pdf` |
| Luận văn (bản nháp) và cách build | `thesis/Thesis.pdf`, [thesis/CLAUDE.md](thesis/CLAUDE.md); web: `/thesis` |
| Hướng dẫn LVTN của khoa (lịch, cấu trúc, chấm điểm, Turnitin) | [THESIS_GUIDE](THESIS_GUIDE.md) |
| Đã đạt yêu cầu nào của hướng dẫn, hạn từng việc (web: `/guide`) | [THESIS_CHECKLIST](THESIS_CHECKLIST.md) |
| Bài báo tham khảo | `references/` |
| Tài liệu thời XNOQuant (không còn đúng) | [archive/README](archive/README.md) |

## Bốn loại tệp

- **Kế hoạch** ([PLAN](PLAN.md)): mỗi việc một dòng — là gì, trạng thái, tới đâu, trỏ tệp chi tiết.
- **Sổ quyết định** ([DECISIONS](DECISIONS.md)): mỗi quyết định một dòng — quyết gì, ngày, ai, lý do một câu.
- **Thiết kế / kết quả hiện hành** (`design/`, [RESULTS](RESULTS.md)): cách làm và con số đang dùng, viết như hôm nay.
- **Nhật ký** (`log/`): quá trình, thử sai, số đo từng lượt, kết luận đã rút lại. Gạch ngang, không xoá.

Ba loại đầu là bản hiện hành: đổi ý thì sửa đúng chỗ, kèm một dòng lý do + ngày. Tệp mới phải có liên kết đi vào từ tệp này hoặc tệp cha.
