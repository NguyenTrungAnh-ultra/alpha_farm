2. Sự Mù mờ về Trách nhiệm: Xung đột Tham số tĩnh (Static Parameter Conflict)Cái gì: Lời nhắc hướng dẫn LLM tạo Macro-Blueprint: div(?, stddev(?, 20)) hoặc ema(?, 50).Tại sao phải cô đọng: Ở đây có sự nhập nhằng giữa Không gian Rời rạc (Cấu trúc) và Không gian Liên tục (Tham số). LLM sinh ra con số 20 hoặc 50 hoàn toàn dựa trên sự đoán mò xác suất (ảo giác) của nó đối với các ví dụ trên mạng, không dựa trên dữ liệu thật. Việc khóa cứng con số 20 ngay từ Tầng 1 sẽ tước đoạt quyền lực của Tầng 3. MCTS sinh ra để tìm chu kỳ tối ưu, nếu LLM đã khóa chu kỳ thành 20, MCTS mất đi một chiều không gian để Tối ưu hóa Cực đại (Risk-seeking).Hành động: Cô đọng Lời nhắc. Ép LLM thay thế mọi tham số số học bằng dấu ? hoặc biến số trừu tượng. Ví dụ: Chuyển div(?, stddev(?, 20)) thành div(?, stddev(?, ?)). Để MCTS tự điền con số 20, 14, hay 50 ở bước chạy bạo lực.Điểm Mù Kiến trúc và Lộ trình Cải thiện (Macro-Blueprint Refactoring)Lời nhắc hiện hành đang "dạy" LLM cách viết mã thay vì ép nó phải "tư duy tài chính". Cần cấu trúc lại Lời nhắc Khởi tạo (Generation Prompt) theo 3 trục sau để khớp nối hoàn hảo với động cơ MCTS:1. Nới lỏng Ràng buộc Điểm Neo Gốc (Root Output Relaxation)Hiện trạng: Lời nhắc ép buộc: "The root of the blueprint must evaluate to a BOOLEAN" (Gốc của biểu thức phải là BOOLEAN như crossed_above).Phân tích Rủi ro: Việc ép gốc là BOOLEAN sẽ khóa hệ thống vào các mô hình Nến (Candlestick) hoặc Giao cắt (Crossovers). Nó giết chết các chiến lược dạng Điểm số (Scoring) hay Xếp hạng (Ranking) có đầu ra là RATIO hoặc CURRENCY.Cải thiện: Cho phép gốc của Blueprint là RATIO hoặc CURRENCY. Ở Tầng 3, Động cơ MCTS/Backtest sẽ tự động bọc gốc đó bằng một hàm Chuẩn hóa $Z-score$ tĩnh và tạo quy tắc cắt lớp $\pm 1.0$ Sigma để sinh ra lệnh Mua/Bán (BOOLEAN) mà không cần LLM phải nhọc công viết logic Giao cắt.2. Tiêm Lệnh cấm Vật lý (FSA Injection)Hiện trạng: Lời nhắc đang cung cấp danh sách chỉ báo và toán tử trống rỗng, để LLM tự do sáng tạo.Cải thiện: Áp dụng bài học từ nghiên cứu LLM-MCTS. Lời nhắc cần có một biến số động (Dynamic Variable) bơm dữ liệu từ sổ tay bộ nhớ của MCTS lên.Thêm khối lệnh: "CRITICAL CONSTRAINT: Do not generate blueprints that share the exact structural topology as the following root patterns: {fsa_forbidden_patterns}".Điều này ép LLM phải "né" các vùng không gian mà MCTS đã cày nát và báo cáo là vô dụng, giải quyết triệt để Hội chứng Suy giảm Trí nhớ Tuyến tính (Linear Amnesia).

1. Bẫy Thứ nguyên do Phân loại sai Logic (The Dimensional Trap)
   Cái gì: Nội dung trong khối TALIB_INDICATORS đang phân loại các hàm theo "Tính chất Kỹ thuật" (Trend, Momentum, Statistics). Ví dụ: ema và vwap nằm chung khối Trend; rsi và macd nằm chung khối Momentum.

Tại sao sai lầm: Sự phân loại này hoàn toàn vô dụng và gây hại cho một hệ thống vận hành bằng Nhất quán Chiều (Dimensional Consistency). Việc thiếu vắng nhãn thứ nguyên khiến LLM không biết rằng macd trả về Giá (CURRENCY) trong khi rsi trả về Tỷ lệ (RATIO). LLM sẽ vô tư viết một Bản thiết kế như add(macd(?,?), rsi(?,?)) vì nghĩ chúng đều là "Momentum". Khi Bản thiết kế này rơi xuống Tầng 3, MCTS sẽ báo lỗi vi phạm vật lý và sập toàn bộ chu trình. Bạn đang cung cấp đạn cho LLM nhưng lại che mắt nó.

2. Mâu thuẫn Cú pháp Quan hệ (Relational Syntax Conflict)
   Cái gì: Trong khối OPERATOR_FUNCTIONS, có dòng hướng dẫn: "Relational: use standard python > and < (e.g., rsi(?, 14) > 50)".

Tại sao sai lầm: Đây là một thảm họa cho Trình biên dịch AST (Tầng 2). Một cây Cú pháp Trừu tượng hoạt động dựa trên cấu trúc đệ quy của các Nút Hàm (Functional Nodes). Việc cho phép LLM chèn các toán tử dạng chuỗi (inline string) như > hay < sẽ phá vỡ hoàn toàn định dạng phân nhánh. MCTS không thể đọc > như một nút gốc hợp lệ để ghép nối.

3. Bẫy Nút Lá Giả (Standalone Candlestick Anomaly)
   Cái gì: Nội dung quy định: "Candlestick (No arguments): doji, hammer, three_black_crows, morning_star". Lời nhắc nhấn mạnh rằng các hàm nến "do not take any arguments or ?" (không nhận tham số hay dấu ?).

Tại sao sai lầm: Thực tế trong TA-Lib, các mô hình Nến luôn đòi hỏi 4 mảng ma trận đầu vào (Open, High, Low, Close). Việc lừa LLM rằng hàm này "không có tham số" sẽ biến chúng thành các Nút Lá (Leaf Nodes) rỗng. Nếu Động cơ MCTS bên dưới không được lập trình riêng một "cầu nối ngầm" để tự động tiêm (inject) 4 ma trận dữ liệu OHLC vào các Nút Nến này khi chạy Backtest, mã thực thi sẽ báo lỗi thiếu tham số đầu vào.

Như thế nào: Tái cấu trúc Nội dung Lời nhắc (Content Restructuring)
Để Lời nhắc khớp nối hoàn hảo với động cơ MCTS, bạn phải đập bỏ cách viết cũ và thiết kế lại theo các quy tắc sau:

1. Tái phân loại theo Thứ nguyên (Dimensional Categorization):
   Thay vì chia theo Trend/Momentum, phải chia danh sách hàm theo Thứ nguyên Đầu ra (Output Dimension).

Ví dụ cấu trúc mới:

[CURRENCY_OUTPUT_FUNCTIONS]: ema, vwap, macd, stddev (Sẽ bị lỗi nếu cộng với RATIO).

[RATIO_OUTPUT_FUNCTIONS]: rsi, adx, roc, pct_change.

[BOOLEAN_OUTPUT_FUNCTIONS]: crossed, crossed*above, crossed_below, and*, or\_.

2. Chuẩn hóa Hàm Quan hệ (Functionalizing Relational Operators):
   Xóa bỏ ngay lập tức hướng dẫn dùng > và <. Phải ép LLM sử dụng toán học dạng hàm nghiêm ngặt.

Ví dụ nội dung cần thay: "Relational: You MUST use greater_than(?, ?) or less_than(?, ?) instead of mathematical symbols."
