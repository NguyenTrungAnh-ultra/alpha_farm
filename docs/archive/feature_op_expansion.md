Giải phẫu và Phân loại Hệ thống Dữ liệu
Toàn bộ danh sách hàng trăm hàm trong hai tệp bạn cung cấp có thể được bóc tách và phân vào 6 nhóm chức năng lõi sau đây.

Nhóm 1: Toán tử Chuỗi Thời gian (Time-Series Operators)
Đây là các hàm dịch chuyển và đo lường khoảng cách dữ liệu dọc theo trục thời gian, thay vì tính toán giá trị tuyệt đối.

Đầu vào: Thường là 1 chuỗi dữ liệu (Unary) và 1 tham số chu kỳ (period).

Các hàm tiêu biểu: shift (dịch dữ liệu về quá khứ), diff (lấy hiệu số), pct_change (tỷ lệ phần trăm thay đổi).

Thứ nguyên Đầu ra: Thay đổi tùy hàm. diff trả về cùng thứ nguyên với đầu vào (CURRENCY - CURRENCY = CURRENCY). pct_change luôn ép kiểu về RATIO (Tỷ lệ).

Nhóm 2: Toán tử Logic & Điều kiện (Boolean & Conditional Operators)
Nhóm này đóng vai trò làm "Công tắc" (Triggers) để chuyển đổi các đường cong liên tục thành các tín hiệu giao dịch nhị phân.

Đầu vào: 1 hoặc nhiều chuỗi dữ liệu (thường là Binary).

Các hàm tiêu biểu: Các hàm giao cắt (crossed, crossed*above, crossed_below), các hàm so sánh (rising, falling, between), và các phép logic (and*, or*, not*).

Thứ nguyên Đầu ra: Dimension.BOOLEAN (Nút này trả về True/False hoặc 1/0). Đáng chú ý có hàm where và value_when có chức năng chọn lọc giá trị dựa trên cờ logic.

Nhóm 3: Chỉ báo Chồng lấp & Xu hướng (Overlap & Trend Indicators)
Đây là các bộ lọc làm mịn (Smoothing filters) được áp trực tiếp lên đường giá để loại bỏ nhiễu (noise).

Đầu vào: Chuỗi giá (thường là Giá Đóng cửa) và tham số chu kỳ.

Các hàm tiêu biểu: Các dải băng (bbands, donchian_upper), các đường trung bình (sma, ema, vwap, kama) và các biến thể phức tạp (mama, tema).

Thứ nguyên Đầu ra: Luôn luôn bảo toàn thứ nguyên đầu vào. Nếu đưa CURRENCY vào sma, đầu ra chắc chắn là CURRENCY.

Nhóm 4: Bộ Dao động & Động lượng (Oscillators & Momentum)
Nhóm này đo lường tốc độ, gia tốc và sức mạnh nội tại của xu hướng, thường bị nén vào một dải băng cố định (ví dụ 0-100).

Đầu vào: Thường yêu cầu nhiều dữ liệu cùng lúc (High, Low, Close).

Các hàm tiêu biểu: rsi, macd, adx, stoch, cci, willr.

Thứ nguyên Đầu ra: Hầu hết đều triệt tiêu thứ nguyên và trả về Dimension.RATIO (hoặc Dimensionless). (Ngoại lệ: macd thực chất là hiệu của 2 đường EMA, nên nó mang thứ nguyên CURRENCY).

Nhóm 5: Thống kê & Biến đổi Toán học (Statistics & Math Transforms)
Nhóm cung cấp các công cụ khai phá tính chất phân phối và dạng hình học của chuỗi dữ liệu.

Các hàm tiêu biểu: Thống kê cơ bản (stddev, var, zscore, beta, correl, linearreg), Biến đổi phi tuyến (log10, sin, tanh, sqrt), và phép toán cơ bản (add, sub, mult, div).

Thứ nguyên Đầu ra: Hàm thống kê định tâm như zscore sẽ ép mọi thứ về RATIO. Các biến đổi phi tuyến như sin hay log10 sẽ phá hủy thứ nguyên vật lý nếu bị áp dụng sai cách (ví dụ Log của 10 USD là vô nghĩa).

Nhóm 6: Nhận diện Mô hình Nến (Candlestick Pattern Recognition)
Một nhánh đặc thù của TA-Lib chuyên săn tìm các hình thái giá cụ thể.

Đầu vào: Bắt buộc phải có đủ 4 ma trận open, high, low, close (Quaternary arity).

Các hàm tiêu biểu: doji, hammer, three_black_crows, morning_star, abandoned_baby.

Thứ nguyên Đầu ra: Số nguyên (Thường là 100, 0, -100 đại diện cho cường độ Bullish/Bearish) hoặc BOOLEAN.

Tại sao và Như thế nào: Ứng dụng Phân loại vào MCTS
Mục tiêu của việc phân loại đống dữ liệu này không phải để làm tài liệu tra cứu, mà là để cấu trúc hóa không gian hành động (Action Space) cho thuật toán MCTS trong file mcts_engine.py.

Hiện tại, hệ thống MCTS của bạn chỉ mới định nghĩa sơ sài vài hàm trong get_operators_for_dimension(Dimension.RATIO). Để "nhốt" hàng trăm hàm mới này vào Cây tìm kiếm, hệ thống cần một "Bộ phân phối Cú pháp" (Syntax Router) hoạt động như sau:

Duyệt ngược từ Yêu cầu Đầu ra (Backward Chaining): Nếu điểm neo ? đang cần một BOOLEAN, MCTS chỉ được phép lấy các toán tử từ Nhóm 2 (như crossed_above) hoặc Nhóm 6 (như doji) để điền vào.

Khớp nối Bậc (Arity Matching): Nếu MCTS chọn hàm crossed(series1, series2) từ Nhóm 2, nó phải tự động sinh ra đúng 2 điểm neo con ? bên trong nút đó. Nếu nó chọn doji(open, high, low, close) từ Nhóm 6, nó phải tạo ra 4 nhánh con tương ứng.

Rủi ro và Sai lầm trong Tư duy Thiết kế
Việc bạn có một danh sách đồ sộ các toán tử là một con dao hai lưỡi. Dưới đây là những sai lầm chết người nếu bạn bê nguyên "đống này" vào MCTS:

1. Ảo tưởng Sự Đa dạng (Illusion of Diversity)
   Trong Nhóm 3, bạn có sma, ema, wma, dema, tema, trima, kama, mama. Về mặt toán học tối ưu hóa, 8 hàm này thực chất chỉ là 1 hàm (đường trung bình trượt) với độ trễ (lag) khác nhau. Nếu bạn thả cả 8 hàm này vào không gian hành động của MCTS, thuật toán sẽ lãng phí hàng vạn vòng lặp (iterations) chỉ để thay thế sma bằng wma và nhận lại cùng một kết quả RankIC.

Cách khắc phục: Chặn đứng sự dư thừa. Chỉ chọn 1 đại diện (ví dụ ema) làm gốc tọa độ cho lớp phủ (Overlap).

2. Bẫy Rò rỉ Tương lai (Look-ahead Bias Trap)
   Trong Nhóm 1, tệp operator.txt có chứa hàm fillna(series, value, method) và replace. Khi MCTS chạy bước rollout() ngẫu nhiên, nó có thể tạo ra một biểu thức dùng fillna với tham số nội suy hướng tới tương lai (forward-looking interpolation) mà backtester không bắt được lỗi. Alpha sinh ra sẽ có Sharpe Ratio > 5.0 (ảo) và cháy tài khoản khi giao dịch thật.

Cách khắc phục: Xóa bỏ hoàn toàn các hàm xử lý dữ liệu khuyết thiếu (fillna, replace) khỏi danh sách tìm kiếm của AI. Việc làm sạch dữ liệu phải là một tiền xử lý cố định (static preprocessing) trước khi MCTS bắt đầu.

3. Khớp nối Mô hình Nến vào Cây Toán học (The Candlestick Impedance Mismatch)
   Nhóm 6 (Mô hình Nến) là một dị biệt. Cây AST của bạn sinh ra các nhánh bất kỳ. Nhưng hàm three_black_crows bắt buộc 4 nhánh con của nó phải luôn luôn là (open, high, low, close) theo đúng thứ tự. Nếu MCTS tạo ra three_black_crows(rsi, volume, sma, macd), mã code sẽ sụp đổ (crash) vì các tham số này không hợp lệ về mặt ngữ nghĩa, dù chúng có thể hợp lệ về mặt thứ nguyên.

Cách khắc phục: Nhóm 6 không được phép xem là các "Toán tử" (Operators) có nhánh con mở. Chúng phải được khai báo trong AST dưới dạng Tính năng Lá (Leaf Features), tương tự như close hay volume, và tự động truy xuất dữ liệu từ môi trường mà không cần MCTS phải tìm kiếm tham số cho chúng.
