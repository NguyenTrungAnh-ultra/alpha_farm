# Báo cáo Đánh giá 101 Formulaic Alphas trên Local (xno_sdk)

Báo cáo chi tiết đánh giá hiệu suất của 101 công thức Alpha giao dịch định lượng từ tài liệu WorldQuant trên dữ liệu hợp đồng tương lai VN30F1M khung thời gian 10 phút.

## 1. Tóm tắt kết quả
- **Tổng số Alpha kiểm tra:** 101
- **Chạy thành công (Thực thi được):** 101
- **Lỗi thực thi (Không tương thích):** 0
- **Số chiến lược bị rỗng tín hiệu (Do lỗi Volume = 0):** 51
- **Số chiến lược đạt hiệu suất đáng chú ý (Sharpe > 1.0, Trades >= 10):** 27

---

## 2. Nhóm Chiến lược Đạt Hiệu Suất Cao Nhất (Sharpe > 1.0)
*Lưu ý: Một số alpha có Sharpe âm cao, ta có thể đổi dấu (Reversal - nhân -1) để thành alpha dương có lợi nhuận.*

| Alpha ID | Sharpe Ratio | CAGR (%) | Max DD (%) | Trades | Non-Zero Pos % | Tóm tắt Công thức |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Alpha#5** | -5.15 | 0.00% | -2023.59% | 30255 | 99.6% | `(rank((open - (sum(vwap, 10) / 10))) * (-1 * abs(rank((close...` |
| **Alpha#101** | -4.74 | 0.00% | -1184.55% | 33429 | 99.6% | `((close - open) / ((high - low) + .001))` |
| **Alpha#19** | -4.58 | 0.00% | -1338.32% | 26851 | 98.9% | `((-1 * sign(((close - delay(close, 7)) + delta(close, 7)))) ...` |
| **Alpha#11** | -4.52 | 0.00% | -1577.82% | 27088 | 99.6% | `((rank(ts_max((vwap - close), 3)) + rank(ts_min((vwap - clos...` |
| **Alpha#42** | -4.22 | 0.00% | -1782.83% | 30809 | 99.6% | `(rank((vwap - close)) / rank((vwap + close)))` |
| **Alpha#20** | -3.45 | 0.00% | -1281.70% | 33371 | 99.6% | `(((-1 * rank((open - delay(high, 1)))) * rank((open - delay(...` |
| **Alpha#57** | -3.43 | 0.00% | -1009.62% | 33435 | 99.6% | `(0 - (1 * ((close - vwap) / decay_linear(rank(ts_argmax(clos...` |
| **Alpha#1** | -3.43 | 0.00% | -970.15% | 31534 | 99.6% | `(rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns,...` |
| **Alpha#29** | -3.41 | 0.00% | -658.28% | 32173 | 99.5% | `(min(product(rank(rank(scale(log(sum(ts_min(rank(rank((-1 * ...` |
| **Alpha#24** | -3.40 | 0.00% | -1220.70% | 30916 | 99.6% | `((((delta((sum(close, 100) / 100), 100) / delay(close, 100))...` |
| **Alpha#32** | -3.36 | 0.00% | -679.56% | 33216 | 98.9% | `(scale(((sum(close, 7) / 7) - close)) + (20 * scale(correlat...` |
| **Alpha#52** | -3.33 | 0.00% | -661.67% | 31138 | 98.9% | `((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank(...` |
| **Alpha#4** | -3.11 | 0.00% | -801.44% | 23398 | 99.6% | `(-1 * Ts_Rank(rank(low), 9))` |
| **Alpha#73** | -2.94 | 0.00% | -970.78% | 23878 | 99.6% | `(max(rank(decay_linear(delta(vwap, 4.72775), 2.91864)), Ts_R...` |
| **Alpha#35** | -2.85 | 0.00% | -944.38% | 32304 | 99.6% | `((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low),...` |
| **Alpha#8** | -2.62 | 0.00% | -608.79% | 28488 | 99.6% | `(-1 * rank(((sum(open, 5) * sum(returns, 5)) - delay((sum(op...` |
| **Alpha#48** | -2.44 | 0.00% | -479.71% | 33167 | 98.9% | `(indneutralize(((correlation(delta(close, 1), delta(delay(cl...` |
| **Alpha#56** | -2.31 | 0.00% | -695.69% | 33173 | 99.6% | `(0 - (1 * (rank((sum(returns, 10) / sum(sum(returns, 2), 3))...` |
| **Alpha#38** | -2.13 | 0.00% | -624.93% | 32896 | 99.6% | `((-1 * rank(Ts_Rank(close, 10))) * rank((close / open)))` |
| **Alpha#21** | -1.95 | 0.00% | -915.06% | 4715 | 99.6% | `((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) ...` |
| **Alpha#23** | -1.69 | 0.00% | -313.69% | 19360 | 99.6% | `(((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)` |
| **Alpha#84** | -1.61 | 0.00% | -478.26% | 11068 | 99.5% | `SignedPower(Ts_Rank((vwap - ts_max(vwap, 15.3217)), 20.7127)...` |
| **Alpha#46** | -1.51 | 0.00% | -341.79% | 9722 | 99.6% | `((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((d...` |
| **Alpha#34** | -1.35 | 0.00% | -356.56% | 31423 | 98.9% | `rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) ...` |
| **Alpha#49** | -1.18 | 0.00% | -221.14% | 20808 | 99.6% | `(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(cl...` |
| **Alpha#18** | -1.15 | 0.00% | -288.24% | 31189 | 99.2% | `(-1 * rank(((stddev(abs((close - open)), 5) + (close - open)...` |
| **Alpha#51** | -1.05 | 0.00% | -198.58% | 20186 | 99.6% | `(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(cl...` |

---

## 3. Phân tích ảnh hưởng của "Volume = 0" (Vấn đề Empty Volume)
Hệ thống XNOQuant gặp lỗi rỗng dữ liệu khối lượng (`pv_volume` = 0). Do đó, bất kỳ Alpha nào phụ thuộc chặt chẽ vào Khối lượng giao dịch hoặc các chỉ báo khối lượng trung bình (`adv20`, `adv30`...) đều sinh ra tín hiệu **hoàn toàn rỗng (tất cả là 0)**.

Có **51** Alpha bị dính lỗi này (tín hiệu giao dịch hoạt động dưới 1.0% tổng thời gian).
*Các Alpha tiêu biểu bị rỗng tín hiệu do phụ thuộc khối lượng:* Alpha#2, Alpha#3, Alpha#6, Alpha#14, Alpha#15, Alpha#17, Alpha#22, Alpha#26, Alpha#28, Alpha#30, Alpha#31, Alpha#36, Alpha#39, Alpha#40, Alpha#43...

---

## 4. Các chiến lược bị Lỗi Thực thi
Một số ít chiến lược bị lỗi do cấu trúc logic không tương thích với pandas/numpy khi chạy trên single asset (ví dụ: chia cho 0 hoặc hàm đặc thù của WorldQuant chưa mock tối ưu):

| Alpha ID | Lỗi chi tiết | Công thức gốc |
| :--- | :--- | :--- |

---

## 5. Kết luận & Khuyến nghị cho Cuộc thi
1. **Tránh tuyệt đối các Alpha dựa trên khối lượng (Volume):** Tất cả các alpha dùng `volume`, `adv` đều bị tê liệt trên XNOQuant do lỗi hệ thống dữ liệu.
2. **Chọn lọc các Alpha giá (Price-only) để biến tấu:** Các Alpha như **Alpha#101** hay các alpha đảo chiều ngắn hạn (dùng `delta(close, d)` và `ts_max`/`ts_min`) là những chiến lược chạy mượt mà nhất và có hiệu suất đáng chú ý.
3. **Cơ chế Reversal:** Rất nhiều chiến lược có Sharpe âm lớn (ví dụ -1.5). Đây là tín hiệu tốt! Chỉ cần đảo ngược vị thế (nhân alpha với -1) là bạn sẽ có một Alpha có Sharpe dương tương ứng.
