# Nhật Ký Thực Chiến & Bài Học Kinh Nghiệm (AGENT_EXP)

Tài liệu này ghi nhận lại các vấn đề phát sinh trong quá trình xây dựng tự động hóa cho XNOQuant, các rủi ro hệ thống, cũng như các bài học rút ra để định hướng cho AI và lập trình viên.

## 1. Rủi Ro Hạ Tầng & Hệ Thống (AI, Web, Data)

- **Biến động Session (Cookies/CDP):** Cơ chế xác thực Web thường xuyên bị quá hạn hoặc từ chối kết nối CDP. Giải pháp hiện tại là mở một giao diện trình duyệt ẩn danh độc lập bằng Playwright cho mỗi chiến lược nhằm đảm bảo độ cách ly. 
- **Giới hạn LLM Quota:** Các vòng lặp tự sửa lỗi (AST Fixer) quá nhiều có thể gây cạn kiệt số lượng token hoặc giới hạn API (Lỗi 429).
- **Trình duyệt chậm (Timeout):** Sandbox trên XNOQuant thường có thời gian phản hồi chậm. Việc cài đặt `timeout` cao (> 60s) và chờ Selector `visible` thay vì click ngẫu nhiên là cần thiết. Bổ sung `force=True` kết hợp gửi phím `Escape` giúp tránh tình trạng Playwright bị lỗi `subtree intercepts` khi gặp các thông báo (toast) nổi.

## 2. Rủi Ro Lượng Hóa & Lệch Pha Dữ Liệu (Data Discrepancy)

Quá trình chạy thực tế so với Local Backtest thường nảy sinh sai số do sự khác biệt về hệ quy chiếu dữ liệu và cơ chế mô phỏng:

- **Khớp lệnh (Execution Bias):** Sự khác biệt giữa giá khớp lệnh tại Local và Web đã được quan sát. Dựa trên quá trình reverse engineering, hệ thống XNOQuant thường ưu tiên khớp tại giá `Close` của nến phát tín hiệu (thay vì giá `Open` của nến sau).
- **Lệch pha Lịch thời gian (Date Shift):** Các timestamp ngày hiển thị trên giao diện Web thường bị xê dịch +1 ngày (VD: ghi nhận lệnh vào Thứ Sáu thay vì Thứ Năm). Tuy nhiên, tổng số ngày giao dịch (Trading Days) để tính CAGR không bị ảnh hưởng.
- **Khoảng hở Dữ liệu (Data Gaps):** Dữ liệu Local từ API DNSE thi thoảng thiếu các thanh (bars) ở quá khứ sâu, trong khi Web có đủ. Việc này khiến các chỉ báo có độ trễ lớn (như SMA dài hạn) bị lệch nhẹ tín hiệu so với hệ thống thực tế.
- **Lệch Tỷ Lệ Khối Lượng (Volume Scaling):** Môi trường Phái sinh trên web XNOQuant có rất nhiều nến mang giá trị `Volume = 0` hoặc cực nhỏ, khác biệt lớn với dữ liệu Local vốn đã được tổng hợp (thường >10 contracts/bar). Do đó, hạn chế tối đa việc sử dụng `Volume` làm biến chính trong chiến lược, thay vào đó ưu tiên các chỉ báo Price-Action (MA, MACD).

## 3. Bài Học Cấu Trúc Mã Nguồn (Coding Experience)

Các quy tắc ngầm của hệ thống XNOQuant đòi hỏi lập trình viên và AI phải sử dụng các "mẹo" để tránh sập AST:

- **Điểm Kỳ Dị Toán Học (Mathematical Singularities):** Vì sự xuất hiện của các nến có `Volume = 0` (hoặc `High - Low = 0`), mọi phép toán lấy Volume hoặc Range làm mẫu số đều có rủi ro trả về `NaN` hoặc `Inf`. Hậu quả là Sandbox đánh rớt chiến lược ngay lập tức. 
  - *Giải pháp tối ưu:* Thay vì cộng số thủ công `1e-8`, hệ thống XNOQuant khuyến khích dùng hàm API `self.op.isfinite(signal)` kết hợp `self.op.zero_ifna()` hoặc `self.op.where()` để "bọc" các điểm kỳ dị và đưa chúng về 0.0 một cách chủ động.
- **State Tracking (Vấn đề lưu giá):** Vì XNOQuant bắt buộc đầu ra là mảng vector (Stateless AST), việc ghi nhận "Giá mở cửa" (Entry Price) rất khó khăn. 
  - *Giải pháp:* Dùng kỹ thuật Pandas nội tuyến `close.where(entry_setup).ffill()` để lưu vết giá vào lệnh, phục vụ tính toán Cắt lỗ động (Trailing Stop/SL).
- **Cấm các tính năng mở rộng:** Tuyệt đối không dùng `.iloc`. Bất kỳ phép gọi nào cố tình bẻ cong luồng vector đều bị từ chối. Xây dựng môi trường ảo (Mock Sandbox) trên Local với lớp `RestrictedSeries` đóng vai trò là "chốt chặn" phát hiện lỗi ngay tại máy trước khi nạp lên web.

## 4. Quản Trị Danh Mục Đầu Tư (Portfolio & Correlation)

- **Thiếu mẫu ngoài chuẩn (Out-of-Sample):** Do tính chất Bayesian Optimizer trên toàn bộ tệp dữ liệu, nguy cơ quá khớp (overfitting) rất cao. Các chiến lược vượt qua vòng này vẫn cần thử nghiệm kỹ lưỡng ở giai đoạn tiếp theo.
- **Nguy Cơ Bị Phạt Trùng Lặp (Correlation Penalty):** Việc chấm điểm tương quan bằng chuỗi lợi nhuận thuần túy đôi khi bỏ sót các "bản sao logic" (logic clones). Sự xuất hiện của kiểm tra tương quan kép (Dual-Correlation) - đối chiếu chéo đồng thời chuỗi PnL và mảng Vị Thế (Positions) - cung cấp lớp lọc đa chiều, giảm thiểu đáng kể nguy cơ bị loại khỏi Leaderboard do vi phạm tính độc nhất.

## 5. Kinh Nghiệm Debug & Phát Triển
- Tập trung phân tách rõ hai luồng logic: `get_feature()` và `get_position()` để mã dễ đọc.
- Bắt và phân tích trực tiếp HTML DOM của trang Web (thông qua `.text-red-500` hoặc `.Toastify`) giúp lấy chính xác nguyên nhân từ chối chiến lược từ Sandbox để khắc phục.

## 6. Tối Ưu Hóa Bộ Đệm (Cache Hit Optimization)

Khi sử dụng các mô hình LLM lớn (như DeepSeek) để sinh dữ liệu hàng loạt:
- **Tách biệt Ngữ cảnh (Context Segregation):** Cần chia tách System Prompt (chứa thông tin tĩnh như luật chơi, danh sách chỉ báo) và User Prompt (chứa thông tin động như yêu cầu vòng lặp). Phần System Prompt phải được giữ nguyên hoàn toàn (byte-for-byte) qua các lần gọi.
- **Hiệu quả:** Phương pháp này dự kiến giảm thiểu lượng Input Tokens phải xử lý lại, hỗ trợ tính năng Cache Hit của nhà cung cấp. Điều này có khả năng giúp giảm chi phí và cải thiện tốc độ phản hồi ở các vòng lặp sau, với giả định hệ thống API hoạt động ổn định.
