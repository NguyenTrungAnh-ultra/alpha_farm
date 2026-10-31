# Sổ quyết định

Mỗi quyết định một dòng, bản hiện hành: đổi ý thì sửa đúng dòng đó, kèm ngày và lý do. Cuộc bàn và số đo dẫn tới quyết định nằm ở [log/](log/).
"Claude" ở cột Ai = Claude chọn, người dùng chưa chốt riêng.

## Câu hỏi nghiên cứu và quy tắc chung

| Quyết định | Ngày | Ai | Lý do |
|---|---|---|---|
| Bỏ RQ2 cũ (toán tử cơ bản vs chỉ báo kỹ thuật); luận văn ghi vào hướng phát triển | 2026-10-29 | người dùng | không trả lời câu chính; chỉ báo vốn là tổ hợp toán tử cơ bản; với ngưỡng phát hiện ≈ IC 0.1 gần chắc "không phân biệt được" |
| Đánh số lại: RQ3 cũ (bằng chứng tìm thấy) thành RQ2; proposal giữ số cũ | 2026-10-29 | người dùng | còn hai câu hỏi |
| RQ1 đổi thước đo: LLM có giúp quy trình phát hiện tín hiệu tốt hơn không, đo bằng bài cài tín hiệu chạy cho từng cấu hình (ngưỡng phát hiện có / không LLM); Sharpe ngoài mẫu các cấu hình chỉ còn là mô tả | 2026-10-31 | người dùng (hướng 1 Claude đề xuất) | 877 ngày ngoài mẫu chỉ phát hiện được chênh Sharpe ≈ 1.0–1.25; bài cài tín hiệu kiểm soát được nhiễu và vẫn phục vụ câu hỏi chính (quy trình có tìm thấy hơn may mắn không) |
| LLM vào vòng tìm kiếm: một vòng phản hồi (top-10 biểu thức đoạn học → LLM viết 10 blueprint mới → MCTS tiếp), thay cho sinh một lần; sửa luật chiều trong prompt (bỏ ví dụ `ts_zscore(?)`), sinh lại bộ blueprint; placebo và bài cài tín hiệu chạy lại trên hệ thống mới. Bài cài tín hiệu RQ1 dùng 2 A kinh điển + 2 A lạ | 2026-10-31 | người dùng (đề xuất của Claude) | sinh một lần thì RQ1 chỉ đo độ phủ của bộ khung; mô hình nhỏ bắt chước ví dụ trong prompt (`ts_zscore` ở 16/20 blueprint) |
| Câu RQ1 chính: cùng giới hạn độ dài công thức, LLM đưa MCTS tới tín hiệu đúng sớm hơn hay chặn đường; đo tỉ lệ tìm lại A theo mốc ngân sách (50.000 = sinh một lần, 100.000 = sau phản hồi), cả theo lượt chấm lẫn thời gian thật | 2026-10-31 | người dùng | blueprint thu vùng tìm 10²⁷ lần; "nhanh hơn" chỉ có nghĩa khi biết A trong hay ngoài vùng |
| Quy tắc dữ liệu thật: mọi lựa chọn ghi vào tài liệu và đóng băng trước lần chạy walk-forward đầu tiên; chạy một lần, không sửa theo kết quả. Mọi lần chỉnh trước đó chỉ chạy trên dữ liệu đã xáo | 2026-10-29 | người dùng | tránh chỉnh theo kết quả |
| Không dùng năm 2025 trong bài cài tín hiệu (giữ ngoài mọi bài test); walk-forward dùng 2025 làm ngoài mẫu | 2026-10-29 | người dùng | 2025 chỉ dùng một lần |
| Chỉ dùng LLM chạy máy (Ollama); gỡ code DeepSeek / Gemini, bỏ `token.txt`, `cookies.txt`, `api.txt` | 2026-10-28 | người dùng | luận văn ghi rõ mô hình local |
| Tệp nháp cũ vào `archive/` | 2026-10-13 | người dùng | |

## Reward và chọn ứng viên

| Quyết định | Ngày | Ai | Lý do |
|---|---|---|---|
| Reward đóng băng cho mọi lần chạy luận văn: `sharpe` (`0.6 · s_sharpe + 0.4 · s_ic`, không cổng). `gated` / `soft` giữ để chạy lại được nhật ký | 2026-10-29 | người dùng | không lệch theo độ dài dữ liệu như Calmar; khớp thước đo chính của proposal; không báo nhầm trên placebo với dữ liệu dài |
| HMM chỉ mô tả rủi ro, không loại chiến lược nào | 2026-10-28 | người dùng (đối chiếu proposal) | bootstrap toàn giai đoạn vì thế không rò vào kết quả |
| Xoá tiêu chí danh mục (`meets_criteria`, `force_add`, loại theo tương quan) và phạt −100 FSA | 2026-10-28 | người dùng | code chết (FSA chỉ kích khi reward > 1.0) |
| Lọc `reward > 0` trước khi chọn: giữ tới khi làm gộp top-5 | 2026-10-28 | người dùng | |
| Top-5 là 5 biểu thức khác nhau, mỗi biểu thức giữ bộ tham số template tốt nhất | 2026-10-28 | người dùng | trước đó top-5 gộp trùng công thức |
| Chọn top-5 trên đoạn kiểm định tách riêng, xếp hạng trong ≤ 100 biểu thức khác nhau tốt nhất của đoạn học | 2026-10-28 | người dùng | reward trong mẫu bị chọn-quá-khớp |

## Bài cài tín hiệu

| Quyết định | Ngày | Ai | Lý do |
|---|---|---|---|
| Báo theo **ngưỡng phát hiện** ứng với lượng dữ liệu, không theo đạt / trượt ở IC 0.05 | 2026-10-29 | người dùng | proposal chỉ ghi các mức IC "for example"; IC 0.05 nằm dưới mức nhiễu của lượng dữ liệu hiện có |
| Luật chọn công thức cài A: blueprint đầu tiên có ≥ 2 ô `?` và gốc NORMALIZED, `?` → `close`, mọi cửa sổ 10; trùng nguyên văn một blueprint ⇒ blueprint kế tiếp | 2026-10-28 | Claude, chốt trước khi xem bộ | A phải biểu diễn được bằng bộ blueprint nhưng không có sẵn |
| Thêm vào luật trên: công thức điền ra hằng ⇒ blueprint kế tiếp; có số hạng chết mà không hằng thì giữ | 2026-10-30 | người dùng | không có tín hiệu để cài |
| β hiệu chỉnh theo IC Spearman trung bình trên 20 hoán vị (seed 1001–1020), một β mỗi độ mạnh | 2026-10-28 | Claude | hiệu chỉnh từng seed buộc β âm để triệt tiêu IC ngẫu nhiên của placebo |
| "Tìm lại gần": \|Spearman\| ≥ 0.7 trên giá trị thô của biểu thức; báo kèm phân bố tương quan | 2026-10-30 | người dùng | RQ2 hỏi có tìm ra quan hệ được cài không; 0.7 là quy ước |
| So thêm vị thế của top-5 với vị thế của A | 2026-10-30 | người dùng | xem công thức tìm được có giao dịch giống A không |

## Walk-forward

| Quyết định | Ngày | Ai | Lý do |
|---|---|---|---|
| Cửa sổ nở dần từ 2018-08-13, đánh giá 6 tháng lăn 6 tháng, 7 cửa sổ 2022-07 → 2025-12, khung 60m | 2026-10-29 | người dùng | 2 năm tìm chỉ phát hiện được IC ≥ 0.1; đánh đổi: 3,5 năm ngoài mẫu ⇒ Sharpe tối thiểu chứng minh được ≈ 1.07 thay vì 0.85 |
| Placebo bộ k, cửa sổ w: mỗi cửa sổ hoán vị riêng, seed tất định theo (k, w) | 2026-10-30 | người dùng | |
| Đoạn kiểm định 12 tháng ngay trước đoạn đánh giá | 2026-10-30 | người dùng (đề xuất của Claude) | bài cài tín hiệu cửa sổ 1 đã chạy với cách chia này |
| Placebo: K = 19, mỗi bộ MCTS seed 1, bộ có Sharpe NaN không tính vào K | 2026-10-30 | người dùng (đề xuất của Claude) | K = 19 là nhỏ nhất cho p = 0.05; bỏ bộ NaN làm p thận trọng hơn |
| Để nguyên ≈ 7% lượt chấm lỗi do biểu thức toàn hằng, ghi vào mục hạn chế | 2026-10-30 | người dùng | như nhau ở mọi cấu hình; sửa thì phải chạy lại mọi kết quả |
| Bài cài tín hiệu: cả ba mức IC đủ 10 seed | 2026-10-30 | người dùng | đồng số seed, tránh chạy thêm chỉ ở ô có kết quả lạ |
| Thứ tự: placebo → cấu hình so sánh → đóng băng → chạy thật một lần | 2026-10-29 | người dùng | thử đường ống trước khi chạm dữ liệu thật |
| Tăng tốc backtest trước khi chạy tiếp; kết quả phải giống hệt bản cũ | 2026-10-30 | người dùng | |

## Bộ blueprint

| Quyết định | Ngày | Ai | Lý do |
|---|---|---|---|
| Sinh lại bộ blueprint bằng prompt mới rồi mới đóng băng; prompt ẩn tên thị trường | 2026-10-29 | người dùng | bộ cũ có 2/20 blueprint chép nguyên ví dụ trong prompt; giảm rò rỉ qua trọng số LLM |
| Chỉnh prompt / tham số bằng lô nhỏ trước, rồi mới sinh bộ thật | 2026-10-29 | người dùng | lô thử không chấm trên dữ liệu nào |
| Tiêu chí bộ thật: 0 trùng nguyên văn ví dụ prompt; không hai blueprint cùng khung; mọi blueprint có ≥ 1 `?` và biên dịch được; 4B, 20 blueprint. 4B không đạt sau 5 lần sinh ⇒ thử `ollama-9b`; không dùng bộ viết tay | 2026-10-28 / 29 | người dùng | |
| Loại blueprint không có ô `?` (áp cho cả `main.py generate`) | 2026-10-28 | người dùng | không có `?` thì MCTS chỉ còn chọn cửa sổ |
| Cấu hình sinh: prompt `anon_shapes`, temperature mặc định 0.3 | 2026-10-29 | Claude | biên dịch lần đầu 100%, gốc đa dạng hơn `anon_rules` |

## Web

| Quyết định | Ngày | Ai | Lý do |
|---|---|---|---|
| Mở từ xa qua Tailscale, không Cloudflare, không tên miền; ⛔ `tailscale funnel` | 2026-10-28 | người dùng | chỉ người dùng xem |
| Từ thiết bị trong tailnet được xem, khởi chạy và dừng | 2026-10-28 | người dùng | |
| Không nhập dữ liệu cũ vào DB | 2026-10-28 | người dùng | tính theo công thức cũ |
| W1 làm cùng bài cài tín hiệu; W3a (web chỉ xem) làm sớm; W2–W5 sau | 2026-10-28 / 29 | người dùng | khó hình dung kết quả qua chat |
