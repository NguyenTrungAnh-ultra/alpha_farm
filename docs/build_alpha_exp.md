# Tài Liệu Ghi Nhận Kinh Nghiệm Phát Triển Alpha (VN30F1M)

Tài liệu này tổng hợp các kết quả thực nghiệm và kinh nghiệm rút ra trong quá trình phát triển các mô hình giao dịch định lượng cho hợp đồng tương lai VN30F1M trên hệ thống XNOQuant. Các đánh giá dưới đây được thiết lập dựa trên kết quả backtest nội bộ (Local Sandbox) và kết quả mô phỏng trên nền tảng Web, trong giới hạn các điều kiện thị trường lịch sử đã được cung cấp.

## 1. Kiểm Thử Hệ Thống Alpha 101 (Cross-Sectional Ranking)
* **Bối cảnh**: Chuyển đổi các công thức Alpha cắt ngang của Zura Kakushadze sang dạng chuỗi thời gian (Time-series) trên một tài sản duy nhất (VN30F1M).
* **Kết quả thực nghiệm**: Tỷ lệ sụt giảm tài sản (Max Drawdown) thường vượt quá giới hạn an toàn.
* **Đánh giá khách quan**:
  - Dựa trên nền tảng lý thuyết, các hàm `rank()` được thiết kế để xếp hạng sức mạnh tương đối giữa nhiều tài sản. Việc áp dụng hàm này cho một tài sản duy nhất dưới dạng `rolling_rank()` làm suy giảm đáng kể khả năng phân loại tín hiệu của thuật toán.
  - Sự phụ thuộc vào dữ liệu khối lượng giao dịch (Volume) của nhiều công thức Alpha 101 tạo ra các điểm kỳ dị (singularities) khi xuất hiện các nến có mức thanh khoản bằng không hoặc quá thấp, dẫn đến sai lệch trong việc ước lượng động lượng.

## 2. Kiến Trúc 1: Basis Arbitrage (Chênh Lệch Cơ Sở - Mean Reversion)
* **Bối cảnh**: Chiến lược giao dịch đảo chiều dựa trên độ lệch chuẩn (Z-score) giữa giá phái sinh VN30F1M và chỉ số cơ sở VN30, kết hợp bộ lọc QuarterOscillate (Bollinger Bands + RSI).
* **Kết quả thực nghiệm**: 
  - **Phiên bản 1 (Thông số chặt chẽ)**: Ghi nhận Max Drawdown ở mức thấp (-13.2%), nhưng tỷ suất lợi nhuận (CAGR 6.6%) và Sharpe (0.82) không đạt chỉ tiêu.
  - **Phiên bản 2 (Nới lỏng thông số)**: Tần suất giao dịch tăng mạnh (174 lệnh), Win Rate giảm xuống 43.75%, dẫn đến mức sụt giảm Max Drawdown lớn (-30.49%) và lợi nhuận âm.
* **Đánh giá khách quan**:
  - Việc đánh giá tín hiệu đảo chiều (Mean-reversion) trên khung thời gian ngắn đòi hỏi sự đánh đổi lớn giữa độ chính xác của tín hiệu và tần suất giao dịch. Dựa trên dữ liệu lịch sử, việc nới lỏng thông số làm tăng xác suất hệ thống chịu ảnh hưởng từ các dao động nhiễu (noise) trong giai đoạn thị trường đi ngang (sideways).
  - Tín hiệu Basis có khả năng mang lại giá trị cao hơn nếu được sử dụng như một bộ lọc (filter) kết hợp, thay vì đóng vai trò là tín hiệu kích hoạt lệnh độc lập.

## 3. Kiến Trúc 2: Đột Phá Xung Lượng Đầu Phiên (Opening Range Breakout - ORB)
* **Bối cảnh**: Chiến lược giao dịch theo động lượng (Momentum) tập trung vào sự phá vỡ vùng giá cân bằng được hình thành trong khoảng thời gian đầu ngày giao dịch.
* **Kết quả thực nghiệm**:
  - Trên Local Sandbox, hệ thống ghi nhận PnL dương nhưng tỷ lệ Drawdown lớn (-48.26%) do giới hạn kỹ thuật của trình giả lập không hỗ trợ tự động đóng lệnh theo thời gian (Time-Gated Exit), khiến vị thế bị giữ qua đêm.
  - Trên Web Sandbox (Phiên bản v2), chiến lược kích hoạt hơn 3000 giao dịch, phí giao dịch tích lũy chiếm 76.08% tài khoản, dẫn đến tỷ suất sinh lời -100%.
* **Đánh giá khách quan**:
  - Cấu trúc dữ liệu trên nền tảng XNOQuant ghi nhận nhiều nến có khối lượng giao dịch cực thấp hoặc bằng 0. Khi điều kiện xác nhận bằng Volume bị gỡ bỏ để tránh lỗi chia số 0, hệ thống ORB trở nên mẫn cảm với các đột phá giá có biên độ hẹp (vốn thiếu sự hỗ trợ của dòng tiền thật), từ đó tạo ra một lượng lớn các giao dịch nhiễu (False Breakouts).
  - Kết hợp với cấu trúc phí giao dịch áp dụng tại thị trường Việt Nam, các chiến lược tần suất cao (High-Frequency Trading) hoặc giao dịch trong ngày với số lượng lệnh lớn có rủi ro bị bào mòn vốn cực kỳ cao, trừ khi hệ thống có bộ lọc xu hướng vĩ mô hoặc thuật toán tối ưu chi phí thực thi hiệu quả.

## 4. Kiến Trúc 3: Lọc Nhiễu Heikin-Ashi Vectơ Hóa (Trung Hạn)
* **Bối cảnh**: Chiến lược bám xu hướng trung hạn sử dụng giao cắt EMA trên dữ liệu nến Heikin-Ashi, áp dụng phương pháp vectơ hóa bằng cấu trúc điều kiện `.where()` để vượt qua hạn chế của vòng lặp và thư viện ngoại lai trên AST.
* **Kết quả thực nghiệm (Local)**:
  - Khung thời gian 30 phút (30m) thể hiện hiệu suất điều chỉnh rủi ro tốt nhất trong nhóm thử nghiệm, với tỷ lệ Sharpe 1.64 và Max Drawdown -15.19%, kèm theo mức lợi nhuận tích lũy trên 400% (giả định chưa tính mức độ trượt giá phức tạp trên web).
* **Đánh giá khách quan**:
  - Cơ chế đệ quy của nến Heikin-Ashi cho thấy khả năng làm mượt biến động giá và giảm thiểu số lượng tín hiệu phá vỡ giả so với nến OHLC truyền thống. 
  - Điều kiện "Nến không có râu ngược chiều" (No shadow filter) có xu hướng hạn chế tần suất giao dịch một cách tương đối, giúp giảm thiểu rủi ro xói mòn vốn từ chi phí giao dịch.
  - Do chiến lược này vận hành độc lập hoàn toàn với dữ liệu Khối lượng (Volume), nó loại bỏ được biến số rủi ro phát sinh từ sự bất đồng bộ dữ liệu Volume trên hệ thống mô phỏng. Hiệu quả thực tế trên Web Sandbox sẽ phụ thuộc vào mức độ tương quan giữa cấu trúc giá của dữ liệu Web và dữ liệu Local đã kiểm thử.

---
**Kết Luận Sơ Bộ**:
Dựa trên chuỗi các bài kiểm tra được thực hiện, có cơ sở để nhận định rằng việc triển khai các chiến lược theo sau xu hướng trung hạn (Trend-Following) kết hợp cùng cơ chế lọc nhiễu giá (điển hình như Heikin-Ashi) thể hiện mức độ tương thích cao hơn với đặc tính vi cấu trúc của VN30F1M và giới hạn nền tảng XNOQuant. Ngược lại, các chiến lược dựa trên tần suất giao dịch cao hoặc phụ thuộc vào tính hoàn hảo của dữ liệu khối lượng hiện đang chứa đựng rủi ro hệ thống lớn.
