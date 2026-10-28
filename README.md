# Alpha Farm

Hệ thống tự tìm **tín hiệu giao dịch có hướng** (Long / Short / Flat) cho hợp đồng tương lai VN30F1M: LLM đề xuất cấu trúc chiến lược, Monte Carlo Tree Search hoàn thiện công thức trên các toán tử chuỗi thời gian `ts_*`, backtest mô phỏng phí, ký quỹ, đáo hạn của phái sinh Việt Nam chấm điểm.

Dự án là phần thực nghiệm của luận văn cử nhân. Câu hỏi nghiên cứu không phải "có làm được không" mà là **cỗ máy có tìm ra thứ gì hơn ngẫu nhiên không** — xem `docs/proposal/thesis_proposal/Thesis_Proposal.pdf`.

> ⛔ **Trạng thái:** pipeline toán tử `ts_*` hiện chưa chạy hết (đứt ở 4 chỗ nối, MCTS không ra ứng viên). Chi tiết và thứ tự sửa: `docs/ROADMAP.md`.

## Tài liệu

| Tệp | Dùng để |
|---|---|
| `docs/ARCH.md` | Kiến trúc đúng như code hiện tại, kèm chỗ đang hỏng |
| `docs/ROADMAP.md` | Kế hoạch hiện hành, việc kế tiếp, câu chờ quyết, nợ |
| `docs/proposal/thesis_proposal/` | Proposal luận văn (LaTeX + PDF) |
| `docs/references/` | Bài báo tham khảo |
| `docs/archive/` | Tài liệu cũ thời XNOQuant, chỉ để tra cứu |

## Cài đặt

- Python 3.12 trong `.venv`, quản lý bằng `uv` (cần để build `hmmlearn`).
- Ollama (bắt buộc): mọi lời gọi LLM đều chạy mô hình local qwen3.5 qua Ollama, không dùng API đám mây.

```bash
uv pip install python-dotenv hmmlearn
```

## Chạy

```bash
.venv/Scripts/python.exe main.py                     # menu tương tác
.venv/Scripts/python.exe main.py generate --n_strategies 20 --model ollama-local
.venv/Scripts/python.exe main.py mcts --iterations 50000 --patience 5000
.venv/Scripts/python.exe main.py full --n_strategies 20 --model ollama-local
```

- `generate`: LLM sinh blueprint vào `results/ideas/`.
- `mcts`: chạy MCTS trên các blueprint đang có trong `results/ideas/` (không có blueprint thì không có gì để chạy), kiểm định HMM, lưu vào `results/portfolio_summary.json`.
- `--model`: `ollama-local` (mặc định, qwen3.5:4b), `ollama-9b` (qwen3.5:9b).

## Kiểm thử

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe benchmark_primitives.py   # so AlphaPrimitives với pandas
```
