# alpha_farm

Hệ thống cung cấp khung sườn tự động (Auto-Gen Framework) để sinh và thử nghiệm các chiến lược định lượng (Quantitative Strategies) trên thị trường phái sinh Việt Nam, phục vụ nền tảng XNOQuant.

## 1. Kiến trúc Hệ thống (XNOQuant Local Framework)

Hệ thống được thiết kế theo mô hình khép kín: Tự động sinh ý tưởng $\rightarrow$ Gen Code $\rightarrow$ Tối ưu hóa tham số cục bộ $\rightarrow$ Backtest mô phỏng Local $\rightarrow$ Nộp và Trích xuất tự động lên Web XNOQuant.

```mermaid
graph TD
    subagent[AI Agents / Users] -->|Tạo Strategy Code| strats[Thư mục: strategies/]
    strats --> pipe(pipeline.py)

    subgraph Local_Environment ["Môi trường Local (Sandbox)"]
        direction TB
        pipe -->|1. Quét & Đọc Code| opt(backtest/optimizer.py)
        opt -->|2. Bayesian Optimization| xno_sdk[xno_sdk/engine.py]

        xno_sdk -->|Signal Vectorized| bt_engine[backtest/engine.py]
        bt_engine -->|Khớp lệnh Bar-by-bar| report[Báo cáo Local PnL & Metrics]

        data[(Dữ liệu DNSE: data/)] -.->|Nạp OHLCV| xno_sdk
    end

    report -->|Lọc chiến lược| agent_res[Thư mục: agent/results/]

    subgraph Web_Environment ["XNOQuant Web"]
        auto_sub(agent/auto_submit.py)
    end

    agent_res -->|Gửi Code đã Tối ưu| auto_sub
    auto_sub -->|Playwright CDP| xno_web((Sàn XNOQuant))
    xno_web -->|Bóc tách Metrics| auto_sub
    auto_sub -->|Lưu CSV| leaderboard((leaderboard.csv))

    style Local_Environment stroke:#666,stroke-width:2px
    style Web_Environment stroke:#666,stroke-width:2px
    style xno_web fill:#28a745,color:#fff
    style leaderboard fill:#f39c12,color:#fff
```

Để xem thông tin kỹ thuật chuyên sâu về cấu trúc hệ thống và quy định (Rules) của sân chơi XNOQuant, vui lòng tham khảo file `ARCH.md`. Để đọc lại bài học thực chiến, hãy tham khảo `AGENT_EXP.md`.
