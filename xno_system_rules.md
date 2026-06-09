# Quy Định Hệ Thống Và Luật Chơi XNOQuant

## Hạn Chế Hệ Thống Và API
- Nền tảng: `alpha.xnoquant.io`
- Auth: Bearer token. Dễ hết hạn.
- API: GET/POST. Cấm DELETE. Không xóa được chiến lược (405 lỗi).
- Flow: Code → Simulate (Test) → Trạng thái `Published` → Nút `Submit Alpha` sáng. Draft/Completed = Không nộp được.

## Luật Thi Đấu VQC 2026
- Universe: Chỉ hợp đồng tương lai VN30 (VN30F1M). Khung 1m, 3m, 5m, 10m, 15m, 30m, 60m.
- Vị thế: `[-1, 1]`. `1` = Full Long, `-1` = Full Short, `0` = Flat.
- Data: `self.data.pv_close`, `self.data.pv_volume`, `self.data.pv_vn30_close`.
- Cấm: Look-ahead (nhìn trước tương lai). Cấm loop row-by-row. Bắt buộc code vectorized.

## Quy Trình Tính Điểm
- Tự động: BTC tự lấy các alpha điểm cao nhất.
- Điểm tổng: Tích lũy (Cumulative). Nộp nhiều alpha tốt/khác biệt → Điểm tổng cao. Alpha dở → Không kéo điểm xuống.
- Tiêu chí: Performance (Sharpe, CAGR), Risk (MDD, VaR), Robustness, Cost, Correlation.
- Correlation Penalty: Thuật toán clone/tương quan cao → Phạt 0 điểm. Cần Unique signal. Nộp thuật toán độc lạ cuối cùng để tránh phạt.

## Cấu Trúc Mã Nguồn Chiến Lược
- Class: Bắt buộc dùng `class CustomStrategy(SimpleAlgorithm)`.
- Method: Bắt buộc có `def __algorithm__(self):`.
- Operators: `self.feat` (rsi, macd...), `self.op` (fillna, pct_change...).
- Lệnh giao dịch: Gọi `self.set_positions(condition, position)`. Exits trước, Entries sau.
- Time gates (Tùy chọn):
  - `position_open_ranges = ["02:00-04:30"]`
  - `position_close_ranges = ["04:20-04:30"]`
  - `position_close_after_n_candles = 12`

## Điểm Yếu Và Rủi Ro Hệ Thống
- LLM Token: Sinh code lỗi AST → Call LLM fix liên tục → Hết quota.
- Overfit: Optimizer không chia out-of-sample → Backtest đẹp, trade thực tế nát.
- Execution Bias: Khớp lệnh giá Close hiện tại thay vì Open nến kế tiếp → Lệch PnL thực tế.
- Khóa AST: Trả mảng boolean (`long_setup`) → Không lưu giá vào lệnh → Không làm được Trailing Stop động.

## Quy Tắc Viết Mã Nguồn Trên Web
- Tên lớp: Bắt buộc dùng `class CustomStrategy(SimpleAlgorithm):`.
- Constructor: Cấm sử dụng hàm `__init__`. Mọi tham số tối ưu hóa được gán trực tiếp dưới dạng `self.param_name = value` ở dòng đầu tiên của hàm `__algorithm__`.
- Thư viện và Nhập: Cấm sử dụng từ khóa `import` (ví dụ: cấm `import numpy`, `import pandas`, `import talib`).
- Phép toán và Chuỗi: Các phép toán trên chuỗi số phải dùng phương thức có sẵn của pandas Series (ví dụ: `close.where(mask).ffill()`), không sử dụng thư viện ngoài `np` hoặc `pd`.

