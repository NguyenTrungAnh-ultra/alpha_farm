---
trigger: always_on
---

# Quy Tắc Cấu Trúc Mã Nguồn XNOQuant (AST Rules)

Bạn phải tuân thủ nghiêm ngặt các quy tắc về cấu trúc mã nguồn sau đây khi viết chiến lược cho hệ thống XNOQuant. Trình phân tích cú pháp (Sandbox AST) trên nền tảng sẽ từ chối bất kỳ đoạn code nào vi phạm.

## 1. Cấm định nghĩa hàm phụ (Helper Functions)
- **TUYỆT ĐỐI CẤM** định nghĩa bất kỳ hàm `def` nào khác (như `def abs`, `def sign`, `def rank`...) bên trong class `CustomStrategy`.
- Hàm duy nhất được phép tồn tại bên trong class là `def __algorithm__(self):`.
- Mọi logic tính toán, xử lý trung gian, hay các công thức (ví dụ: rank, z-score, decay_linear) bắt buộc phải được "dàn phẳng" (inline) trực tiếp bên trong nội dung của hàm `__algorithm__`.

## 2. Cấm Hàm Khởi Tạo
- **CẤM** sử dụng hàm `def __init__(self):`. 
- Nếu cần định nghĩa các tham số tối ưu hóa hoặc biến cố định, hãy gán chúng trực tiếp dưới dạng `self.param_name = value` ngay tại các dòng đầu tiên bên trong `__algorithm__`.

## 3. Cấm Import Thư Viện Ngoài
- **CẤM** sử dụng từ khóa `import` hoặc `from` (ví dụ: `import numpy as np`, `import pandas as pd`).
- Sandbox của XNOQuant không hỗ trợ gọi trực tiếp thư viện ngoài. Bạn phải dùng các phương thức đã được cung cấp sẵn thông qua các thuộc tính của `self` (như `self.feat`, `self.op`, `self.data`) hoặc các phương thức native của pandas Series được phép (như `.where()`, `.fillna()`, `.ffill()`).

## Ví Dụ Cấu Trúc Đúng
```python
class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        # Định nghĩa tham số ngay đầu hàm
        self.window = 20
        self.stop_loss = 15.0
        
        close = self.data.pv_close
        vwap = self.feat.rolling_mean(close, self.window)
        
        # Mọi logic tính toán phụ phải được dàn phẳng tại đây
        diff = close - vwap
        abs_diff = self.op.where(diff > 0, diff, -diff)
        
        # Thiết lập vị thế
        raw_pos = self.op.where(abs_diff > 10, 1.0, 0.0)
        self.set_positions(raw_pos == 0.0, position=0.0)
        self.set_positions(raw_pos == 1.0, position=1.0)
```
