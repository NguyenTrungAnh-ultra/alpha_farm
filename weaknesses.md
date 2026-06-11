# Điểm Yếu Dự Án XNOQuant

## Rủi Ro AI & Hạ Tầng

1. **Cookie hết hạn/đổi định dạng**
   - Cookie web dễ hết hạn. Google đổi mã hóa payload → Hỏng `gemini_client.py`. Google chặn IP.

2. **Hết Quota LLM**
   - Pipeline call LLM nhiều lần (Idea → Code → Fix AST). Dễ dính lỗi 429 Too Many Requests → Đứt gãy farm đêm.

3. **Lỗi format code XNO [ĐÃ KHẮC PHỤC]**
   - *Vấn đề:* XNO cấm loop, bắt vectorized `self.feat`. Gemini hay quên luật. Validator gọi sửa liên tục → Tốn tài nguyên.
   - *Giải pháp:* Phát triển thành công `xno_sdk` giả lập Sandbox với `RestrictedSeries` để bắt lỗi vi phạm phương thức cấm (`.iloc`, `.mean()`, `.std()`...) trực tiếp tại Local trước khi đẩy lên web.

4. **Ý tưởng chiến lược cũ kỹ**
   - LLM tái chế chỉ báo kinh điển (RSI, EMA, MACD). Thiếu lợi thế thực tế (edge) trên thị trường.

---

## Rủi Ro Lượng Hóa & Hệ Thống

5. **Thiếu Out-of-Sample (OOS) Testing**
   - Optimizer tối ưu toàn bộ data, không chia OOS. Dễ quá khớp (overfitting) → Backtest đẹp, trade thật lỗ.

6. **Sai số khớp lệnh (Execution Bias) [ĐÃ GIẢI QUYẾT]**
   - *Vấn đề:* Engine giả định khớp giá Close nến hiện tại. Thực tế khớp Open nến sau → Lệch PnL thực tế lớn.
   - *Giải pháp:* Qua reverse engineering lịch sử PnL và khớp lệnh, xác nhận XNOQuant thực sự khớp lệnh tại giá `Close` của nến phát tín hiệu. Đồng bộ hóa 100% các công thức chỉ số (Sharpe dùng constant capital, Volatility dùng rolling, CAGR dùng Trading Days) loại bỏ hoàn toàn sai số.

7. **Stateless AST (Bị trói bởi Mask) [ĐÃ KHẮC PHỤC]**
   - *Vấn đề:* Đầu ra dạng mảng boolean (`long_zone`/`short_zone`) → Không lưu được giá vào lệnh (`entry_price`). Không thể làm Trailing Stop, chốt lời từng phần, quản vị thế động.
   - *Giải pháp:* Sử dụng mẫu lập trình vector `close.where(entry_setup).ffill()` để lưu vết giá vào lệnh trực tiếp trong môi trường sandbox của XNO. Đã áp dụng thành công cho cơ chế cắt lỗ động trong `MeanRev_CCI_LinearReg`.

8. **Tương quan danh mục sơ sài [ĐÃ KHẮC PHỤC]**
   - *Vấn đề:* Chỉ sử dụng tương quan Pearson trên chuỗi lợi nhuận (daily returns) có thể không phát hiện được các chiến lược trùng lặp về mặt logic vào lệnh (logic clones) nhưng có sự sai lệch nhỏ về mặt thời điểm. Điều này dẫn đến nguy cơ bị hệ thống XNOQuant phạt điểm trùng lặp.
   - *Giải pháp:* Nâng cấp cơ chế kiểm tra tương quan trong `PortfolioManager` thành kiểm tra kép (Dual-Correlation). Hệ thống hiện tại tính toán cả tương quan Pearson của chuỗi lợi nhuận (daily returns) và tương quan Pearson của mảng vị thế/tín hiệu (position/signal arrays) giữa chiến lược mới và các chiến lược đã có. Thử nghiệm thực tế cho thấy cơ chế này giúp nhận diện chính xác các chiến lược có logic tương đồng cao, từ đó nâng cao tính đa dạng của danh mục đầu tư.
