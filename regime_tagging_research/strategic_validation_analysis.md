# Báo Cáo Nghiên Cứu: Đánh Giá Tính Bền Bỉ Của Alpha Bằng HMM & Monte Carlo

Tài liệu này tổng hợp toàn cảnh dự án nghiên cứu đánh giá "edge" (lợi thế) thực chất của các Alpha. Báo cáo không chỉ dừng ở việc tối ưu hóa ngưỡng thống kê, mà còn chỉ điểm các điểm mù trong thiết kế thực nghiệm và đề xuất quy trình tái cấu trúc hệ thống.

---

## 1. Mục Tiêu Nghiên Cứu & Thiết Kế Thí Nghiệm
**Mục tiêu**: Loại bỏ các Alpha may mắn/overfit, giữ lại các Alpha thực sự có năng lực sống sót khi cấu trúc thị trường thay đổi bất lợi.

**Kiến trúc Pipeline**:
1. **Gaussian Hidden Markov Model (HMM)**: Nhận diện và phân chia các trạng thái thị trường (Regimes) dựa trên phân phối lợi nhuận/biến động (2 trạng thái cho khung dài, 3 trạng thái cho khung ngắn).
2. **Markov Chain Monte Carlo (MCMC) Bootstrapping**: Sinh hàng loạt chuỗi tương lai giả lập dựa trên ma trận xác suất chuyển trạng thái của HMM, kết hợp Block Bootstrapping để giữ tính tự tương quan (autocorrelation).
3. **Kịch bản Stress-test**: Tăng 1.5 lần xác suất chuyển sang và mắc kẹt ở trạng thái "Panic" để đo lường năng lực phòng thủ của Alpha.

---

## 2. Quá Trình Tinh Chỉnh Bộ Quy Tắc Đánh Giá (Validation Rules)
Thử nghiệm trên 149 Alpha thực tế, chúng ta đã tiến hóa qua 3 vòng lặp để khắc phục lỗ hổng toán học:

* **Vòng 1 (Luật cứng nhị phân)**: Cắt theo Percentile $\le 85\%$ và duy trì 50% Sharpe. Hậu quả là tiêu diệt oan hàng loạt Alpha tốt ở khung dài do chúng tự nhiên rơi vào vùng outlier.
* **Vòng 2 (Mở đường lùi bằng điểm Stress)**: Bù đắp cho Vòng 1 bằng cách ưu tiên Alpha có Sharpe Stressed $\ge$ Normal. Hậu quả là khung ngắn (3m/5m) lọt lưới $\sim 79\%$, vì lợi nhuận của nhóm này sát $0$ nên chênh lệch Stress $>$ Normal chỉ là nhiễu ngẫu nhiên.
* **Vòng 3 (Thêm Rule 4 chốt chặn)**: Bổ sung điều kiện **MC Sharpe $\ge 0.3$** để lọc nhiễu ngẫu nhiên. Kết quả thu được một đường cong Pass Rate hoàn hảo và logic:

| Khung thời gian | Số Alphas (N) | Pass Rate | Phân tích Thống kê |
|---|---|---|---|
| 1m / 3m / 5m | 64 | **0.0%** | Loại bỏ hoàn toàn rác nhiễu vi mô |
| 10m / 15m | 44 | **15.0% - 16.7%** | Tỷ lệ sống sót thấp/trung bình |
| 30m | 25 | **48.0%** | Giữ được 50% tinh hoa |
| 60m (1H) | 16 | **93.8%** | Robust nhất, chống nhiễu tuyệt đối |

---

## 3. Các Lỗ Hổng Kiến Trúc & Cảnh Báo Phương Pháp Luận (Caveats)

Dù đường cong trên rất thuyết phục, cuộc điều tra sâu hơn đã chỉ ra 4 vấn đề lớn cần đính chính để tránh kết luận quá khái quát hóa (over-generalization):

### A. Nguyên nhân thực của 0% Pass Rate: Scale-Mismatch tại MCTS
Việc 1m/3m/5m rụng 100% không chứng minh "khung ngắn tự thân vô vọng", mà chỉ ra **lỗi cấu hình tại tầng sinh Alpha**.
* MCTS đang dùng tệp chỉ báo tĩnh: `PERIODS = [5, 10, 14, 20, 30, 60]` chung cho mọi timeframe. 
* Hệ quả: Ở 1m, 14 bars là 14 phút (nhiễu vi mô). Hệ thống ép khung 1m phải giao dịch liên tục (overtrading) khiến chi phí giao dịch tàn phá sạch hiệu suất mô phỏng.

### B. "Oan sai" sát biên: Giới hạn bản thể của Ngưỡng cứng
Bất kỳ ngưỡng cứng nào (như 0.3) cũng sinh ra vùng xám. Trong 12 case sát biên bị loại:
* Có chiến lược **thực sự bị loại oan** (VD: Ema_Atr_60m có Drawdown an toàn tuyệt đối -13.5%).
* Nhưng cũng có chiến lược **hoàn toàn xứng đáng bị loại** (VD: Dema_Ema_Atr_10m có Drawdown lên tới -62%). Không thể gộp chung thành một nhóm "chất lượng", mà bắt buộc phải phân loại dựa trên rủi ro (Risk-Adjusted).

### C. Cảnh báo rủi ro cỡ mẫu nhỏ (Small Sample Overfitting)
Sự đơn điệu của Pass Rate tuy đẹp nhưng đang dựa trên cỡ mẫu nhỏ ở từng nhóm (ví dụ: chỉ có 14 Alpha ở 3m, 16 Alpha ở 60m). Với $N=14-31$, chỉ cần một vài Alpha may/rủi cũng đủ làm dịch chuyển 10-15 điểm phần trăm. Cần thận trọng để **không overfit kết luận luận điểm vào đúng 149 Alpha này**.

### D. Biến số gây nhiễu: Số lượng mô phỏng (N paths) không đồng nhất
Trong tập dữ liệu, số lượt chạy MC dao động từ 50 đến 300 paths tùy timeframe. Theo định lý giới hạn trung tâm, $N$ thấp sẽ sinh ra sai số chuẩn (phương sai) cực lớn. Sự chênh lệch phương sai giữa các nhóm làm suy yếu độ tin cậy khi so sánh chéo Pass Rate.

---

## 4. Kế Hoạch Hành Động & Phân Bổ Ưu Tiên (Next Steps)

Cần phân định rõ thứ tự ưu tiên giữa việc thay đổi cốt lõi (Input) và thay đổi cách chấm điểm (Output).

### 🔴 ƯU TIÊN 1 (MỨC ĐỘ: CAO) - Nâng cấp Input (Sinh Alpha & Thực nghiệm làm sạch)
*Giá trị kỳ vọng: Khắc phục lỗi gốc, nâng cao chất lượng Alpha cho TOÀN BỘ các khung thời gian.*

1. **Sửa lỗi Scale-Mismatch trong MCTSEngine**: Scale động `PERIODS` theo timeframe. (VD: nhân hệ số 20x-60x cho khung 1m để 14-period ở 1m tương đương ý nghĩa về mặt thời gian vật lý với 14-period ở 60m).
2. **Chuẩn hóa biến gây nhiễu**: Cố định N mô phỏng (ví dụ $N=300$) cho mọi timeframe trong quá trình MCMC.
3. **Thực nghiệm xác nhận chéo (Replication)**: Chạy MCTS sinh ra một batch Alpha hoàn toàn mới cho 1m/3m/5m và validate lại. 
   * *Mục đích*: Xác nhận dứt điểm xem Pass Rate của 1m có còn là 0% do bản chất transaction cost, hay thực sự đã tăng lên nhờ fix lỗi config. Đồng thời xác nhận đường cong Pass Rate không bị overfit với 149 Alpha cũ.

### 🟡 ƯU TIÊN 2 (MỨC ĐỘ: TRUNG BÌNH) - Nâng cấp Output (Đánh giá Validation)
*Giá trị kỳ vọng: Tối ưu hóa việc lọc các Alpha đã sinh ra, loại bỏ vấn đề oan sai do ngưỡng cứng.*

1. **Chuyển sang Composite Scoring**: Bỏ mô hình Pass/Fail nhị phân. Xếp hạng Alpha theo điểm số liên tục bằng cách tính trọng số tổng hợp:
   $Score = w_1(1 - Percentile) + w_2\frac{MC\_Sharpe}{Hist\_Sharpe} + w_3(1 - |DD_{5th}|) + w_4(Stressed - Normal)$
2. **Quy trình Calibrate Trọng số nghiêm ngặt**: Chuyển đổi sang Composite Score không tự động giải quyết vấn đề "chọn số tùy ý", nó chỉ dời bài toán sang việc gán $w_1 \rightarrow w_4$. Bắt buộc phải chạy **Hồi quy (Regression/Calibration)** bằng chính tập dữ liệu 149 Alpha hiện có (hoặc lý tưởng nhất là Out-of-Sample/Live data) để tìm ra bộ trọng số tối ưu về mặt toán học, tuyệt đối không gán đều hoặc áng chừng bằng cảm tính.
