# Công trình liên quan: LLM trong đầu tư và tìm alpha

Đọc ngày 2026-10-31 qua trang arXiv / tóm tắt, chưa đọc hết toàn văn mọi bài. Khoá `\bibitem` trong proposal ghi trong ngoặc; bài chưa có khoá là chưa vào danh mục tài liệu (phải đối chiếu trang nhà xuất bản / arXiv trước khi thêm).

## LLM trong đầu tư nói chung

| Hướng | Bài tiêu biểu | LLM làm gì | Kiểm chứng |
|---|---|---|---|
| Đọc tin → điểm cảm xúc → giao dịch | Lopez-Lira & Tang, arXiv 2304.07619 | chấm tiêu đề tin tốt / xấu cho từng cổ phiếu | dự báo lợi suất ngày ngoài mẫu; mô hình lớn mới dự báo được, mô hình nhỏ (GPT-1/2, BERT) không |
| Rò rỉ qua trọng số (look-ahead) | Glasserman & Lin, arXiv 2309.17322; Gao, Jiang & Yan, arXiv 2512.23847 | — | ẩn tên công ty để đo rò rỉ; kiểm định thống kê khả năng prompt có trong dữ liệu huấn luyện. Ghi nhớ làm phồng năng lực dự báo |
| Agent giao dịch | FinMem, FinAgent, TradingAgents (tổng quan arXiv 2408.06361) | agent nhiều vai, bộ nhớ, tự phản tỉnh, ra lệnh mua / bán | FINSABER (arXiv 2505.07078) chỉ ra: đoạn thử 3–6 tháng, 3–6 mã, chọn mã theo cả giai đoạn; thử dài hơn thì lợi thế mất |
| Tổng quan | Zhao và cs., arXiv 2401.11641; Jadhav & Mirza, Frontiers in AI 2025 (84 bài) | — | khoảng trống chung: kiểm chứng thực tế, độ tin cậy |

## LLM tìm alpha công thức

| Bài | LLM làm gì | Tìm kiếm | Dữ liệu | So với | Cô lập vai trò LLM? |
|---|---|---|---|---|---|
| Alpha-GPT (wang2023) | dịch ý tưởng người → công thức (bản v2: Llama 3 70B) | người trong vòng lặp | WorldQuant IQC, cổ phiếu Trung Quốc / Mỹ, không ghi giai đoạn | người thi, nghiên cứu viên mới vào nghề | không |
| AlphaAgent (tang2025) | agent đặt giả thuyết → công thức; phạt trùng AST, phạt độ phức tạp | vòng lặp agent | CSI 500, S&P 500, OHLCV, thử 2021–2024 | RD-Agent, thư viện alpha | không thấy trong tóm tắt |
| Alpha Jungle (shi2026) | prior sinh / sửa công thức trong từng nút | MCTS, UCT, reward = backtest | A-share CSI 300 / 1000, học 2011–2020, thử 2021–2024; S&P 500 | GP, DSO, AlphaGen, AlphaForge, CoT, ToT, FAMA | **không**: không có bản bỏ LLM, không có tìm ngẫu nhiên cùng ngân sách; chạy một lần, không kiểm định ý nghĩa |
| RD-Agent-Quant (Li và cs., arXiv 2505.15155, NeurIPS 2025) | agent nghiên cứu + agent viết code, tối ưu cả yếu tố lẫn mô hình | bandit chọn hướng | CSI 300, học 2008–2014, kiểm định 2015–2016, thử 2017-01 → 2020-08; phụ lục CSI 500, NASDAQ 100 | thư viện yếu tố cổ điển, mô hình chuỗi thời gian | không; chỉ so cách chọn hướng (ngẫu nhiên / LLM / bandit) |
| Chain-of-Alpha (arXiv 2508.06312) | hai chuỗi: sinh và tối ưu yếu tố, không cần người | vòng lặp LLM | — | Alpha-GPT, AlphaAgent | **đã rút khỏi arXiv** (2025-08); không dùng |

**Alpha Jungle, kiểm tra rò rỉ:** hỏi thẳng GPT-4.1 / Gemini / Deepseek viết công thức dự báo lợi suất 10 ngày CSI 300 ⇒ IC ≈ 0.012–0.013, không khác alpha LLM ngẫu nhiên, thấp xa khung (0.053) ⇒ kết luận LLM không nhớ sẵn công thức tốt. **Độ nhạy theo mô hình:** 5 mô hình (có Qwen3-235B), IC LightGBM 0.0376–0.0399, IR dao động mạnh (0.71 → 1.98).

## Bảng kiểm phương pháp

Đọc toàn văn bản HTML trên arXiv (Alpha Jungle v3, AlphaAgent v1, Alpha-GPT v2, RD-Agent-Quant v2) ngày 2026-10-31; RD-Agent-Quant mới đọc ≈ 60% (chưa hết phụ lục). ✅ có · ⚠️ một phần / không rõ · ❌ không có.

| Mục | Alpha-GPT | AlphaAgent | Alpha Jungle | RD-Agent-Quant | Luận văn |
|---|---|---|---|---|---|
| 1. Đoạn thử tách theo thời gian, không dùng để chọn | ❌ không ghi ngày; điểm dừng chọn từ đường IC ngoài mẫu | ⚠️ có đoạn kiểm định 2020 nhưng không nói dùng thế nào; "tổ hợp tốt nhất" không rõ chọn theo gì | ⚠️ tách theo thời gian, không thấy đoạn kiểm định riêng | ⚠️ có ba đoạn; không nói kết quả vượt SOTA được giữ theo đoạn nào | ✅ học / kiểm định / đánh giá; walk-forward 7 cửa sổ; đóng băng trước khi chạy thật |
| 2. Phí giao dịch, vòng quay | ❌ | ⚠️ có phí, không báo vòng quay | ✅ phí 0.15%, vòng quay là một tiêu chí | ⚠️ "phí thực tế" ở phụ lục, chưa kiểm số | ✅ phí theo hợp đồng, ký quỹ, gọi ký quỹ |
| 3. Độ dài / độ rộng đoạn thử | ❌ không ghi | ✅ ≈ 4 năm, 2 thị trường | ✅ ≈ 4 năm, A-share + S&P 500 | ✅ 3,6 năm + phụ lục 1,5 năm | ⚠️ 3,5 năm, một hợp đồng |
| 4. Nhiều lần chạy, kiểm định ý nghĩa | ❌ | ⚠️ 20 lượt cho hai hệ LLM, đối thủ một lượt; không kiểm định | ❌ kết quả chính một lượt | ⚠️ đối thủ 5 seed báo trung vị; cố ý không báo sai số | ✅ 10 seed bài cài tín hiệu, Fisher; 5 seed walk-forward |
| 5. Cùng ngân sách, bỏ LLM, tìm ngẫu nhiên | ❌ so với người | ❌ khác mô hình nền, khác số lượt; không bỏ LLM, không ngẫu nhiên | ❌ không bỏ LLM, không ngẫu nhiên cùng ngân sách | ⚠️ cùng 12 giờ; không bỏ LLM | ✅ cùng 100.000 lượt chấm; MCTS không LLM, tìm ngẫu nhiên |
| 6. Rò rỉ qua trọng số LLM | ⚠️ chỉ phần thi trực tiếp | ❌ | ✅ hỏi LLM viết thẳng ⇒ không hơn ngẫu nhiên | ⚠️ LLM chỉ thấy lược đồ dữ liệu; ngày cắt "gần như" trước đoạn thử | ⚠️ ẩn tên thị trường; chưa tra ngày cắt |
| 7. Báo số cấu hình đã thử / chỉnh cho kiểm định nhiều lần | ❌ | ⚠️ 20 × 5 vòng, không chỉnh | ❌ | ❌ | ⚠️ placebo lặp cả quy trình (chọn-quá-khớp nằm trong phân phối placebo); SPA / DSR chưa làm |

Kiểm chứng chung của nhóm bài: placebo ❌ ở cả bốn bài; bài cài tín hiệu ❌ ở cả bốn bài.

## Khoảng trống luận văn lấp

- Không bài tìm alpha bằng LLM nào thấy được có: (1) so với bản bỏ LLM cùng ngân sách, (2) tìm ngẫu nhiên cùng ngân sách, (3) placebo trên dữ liệu không có tín hiệu, (4) bài cài tín hiệu đo ngưỡng phát hiện, (5) nhiều seed và kiểm định ý nghĩa. Thước đo chung là IC / IR trên một đoạn thử, một lần chạy.
- Mọi bài dùng cổ phiếu, cắt ngang (xếp hạng cổ phiếu); luận văn là một hợp đồng tương lai, chuỗi thời gian, có phí và ký quỹ.
- Mọi bài dùng mô hình đóng lớn (GPT-3.5 → GPT-4.1); luận văn dùng mô hình 4B chạy máy ⇒ kết quả chỉ nói về lớp mô hình nhỏ (Lopez-Lira & Tang: năng lực dự báo tăng theo cỡ mô hình).
- Ẩn tên thị trường trong prompt cùng ý với cách ẩn tên công ty của Glasserman & Lin.
