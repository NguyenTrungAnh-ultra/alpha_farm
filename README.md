# alpha_farm

Hệ thống cung cấp khung sườn tự động (Auto-Gen Framework) để sinh và thử nghiệm các chiến lược định lượng (Quantitative Strategies) trên thị trường phái sinh Việt Nam, phục vụ nền tảng XNOQuant.

## 1. Kiến trúc Hệ thống (XNOQuant Local Framework)

Hệ thống được thiết kế theo mô hình khép kín: Tự động sinh ý tưởng $\rightarrow$ Gen Code $\rightarrow$ Tối ưu hóa tham số cục bộ $\rightarrow$ Backtest mô phỏng Local $\rightarrow$ Nộp và Trích xuất tự động lên Web XNOQuant.

```mermaid
graph TD
    subagent[AI Agents] -->|1. Sinh ý tưởng JSON| agent_ideas[Thư mục: agent/results/ideas]
    agent_ideas -->|2. Chuyển đổi Idempotent| convert(agent/convert_ideas.py)
    
    subgraph Local_Environment ["Môi trường Local (Sandbox)"]
        direction TB
        convert -->|Validate Sandbox| xno_emu[xno_sdk/emulator.py]
        xno_emu -->|Syntax OK| agent_res[Thư mục: agent/results/]
        
        agent_res -->|Đọc file chưa tối ưu| opt(optimize_all_v2.py)
        opt -->|Bayesian Search| xno_emu
        opt -->|3. Ghi đè Regex & Đóng mộc| agent_res
    end

    subgraph Web_Environment ["XNOQuant Web"]
        auto_sub(submit_all.py)
    end

    agent_res -->|4. Gửi Code đã Tối ưu| auto_sub
    auto_sub -->|Playwright CDP| xno_web((Sàn XNOQuant))
    xno_web -->|Bóc tách Metrics| auto_sub
    auto_sub -->|Dời file hoàn tất| pushed[Thư mục: agent/results/pushed/]

    style Local_Environment stroke:#666,stroke-width:2px
    style Web_Environment stroke:#666,stroke-width:2px
    style xno_web fill:#28a745,color:#fff
    style pushed fill:#f39c12,color:#fff
```

Để xem thông tin kỹ thuật chuyên sâu về cấu trúc hệ thống và quy định (Rules) của sân chơi XNOQuant, vui lòng tham khảo file `ARCH.md`. Để đọc lại bài học thực chiến, hãy tham khảo `AGENT_EXP.md`.
