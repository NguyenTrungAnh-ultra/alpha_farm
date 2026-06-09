# Điểm Yếu Dự Án XNOQuant

## Rủi Ro AI & Hạ Tầng

1. **Cookie hết hạn/đổi định dạng**
   - Cookie web dễ hết hạn. Google đổi mã hóa payload → Hỏng `gemini_client.py`. Google chặn IP.

2. **Hết Quota LLM**
   - Pipeline call LLM nhiều lần (Idea → Code → Fix AST). Dễ dính lỗi 429 Too Many Requests → Đứt gãy farm đêm.

3. **Lỗi format code XNO**
   - XNO cấm loop, bắt vectorized `self.feat`. Gemini hay quên luật. Validator gọi sửa liên tục → Tốn tài nguyên.

4. **Ý tưởng chiến lược cũ kỹ**
   - LLM tái chế chỉ báo kinh điển (RSI, EMA, MACD). Thiếu lợi thế thực tế (edge) trên thị trường.

---

## Rủi Ro Lượng Hóa & Hệ Thống

5. **Thiếu Out-of-Sample (OOS) Testing**
   - Optimizer tối ưu toàn bộ data, không chia OOS. Dễ quá khớp (overfitting) → Backtest đẹp, trade thật lỗ.

6. **Sai số khớp lệnh (Execution Bias)**
   - Engine giả định khớp giá Close nến hiện tại. Thực tế khớp Open nến sau → Lệch PnL thực tế lớn.

7. **Stateless AST (Bị trói bởi Mask)**
   - Đầu ra dạng mảng boolean (`long_zone`/`short_zone`) → Không lưu được giá vào lệnh (`entry_price`). Không thể làm Trailing Stop, chốt lời từng phần, quản vị thế động.

8. **Tương quan danh mục sơ sài**
   - Dùng Pearson correlation lọc trùng Equity Curve. Bỏ qua Tail Risk (tương quan ẩn khi thị trường sụp đổ đồng loạt).
