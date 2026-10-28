# Kế hoạch — Web điều khiển và theo dõi (chưa làm)

Bản hiện hành. Đổi ý thì sửa đúng chỗ, kèm một dòng lý do + ngày.
Nguồn: yêu cầu người dùng 2026-10-28 ("web chạy local, SQLite làm DB; chọn bắt đầu từ bước nào, đang chạy bước nào, bước đó xong bao nhiêu alpha").
Đổi 2026-10-28: bỏ Cloudflare, dùng Tailscale (người dùng: chỉ mình họ xem, đã có Tailscale; Cloudflare cần thuê tên miền).

Trạng thái: ✅ W1 xong 2026-10-28 (test `tests/test_progress_hooks.py`, 12 ca); W2–W6 chờ việc 3 có kết quả.

## 1. Mục tiêu

- Khởi chạy pipeline từ trình duyệt, chọn **bắt đầu từ bước nào** và tham số, không phải gõ lệnh.
- Thấy **đang chạy bước nào**, mỗi bước xong bao nhiêu việc, đã ra bao nhiêu ứng viên / alpha, còn bao lâu.
- Xem kết quả (công thức, chỉ số, đường vốn, kiểm định) trực quan hơn đọc JSON / CSV.
- Xem được từ thiết bị khác của người dùng (Mac, điện thoại) qua mạng Tailscale riêng, trong khi máy tính chạy tính toán vẫn là máy này.

Không phải mục tiêu: thay CLI (`main.py` vẫn chạy như cũ), chạy nhiều lượt song song, cho người khác dùng, công khai lên Internet.

**Ràng buộc luận văn:** web chỉ **quan sát và ra lệnh**, không đổi phép tính. Cùng tham số + seed thì chạy qua web và chạy qua CLI phải ra cùng kết quả (có test canh).

## 2. Kiến trúc

```
Trình duyệt (Mac / điện thoại, đã vào tailnet)
   │ HTTPS  https://<tên-máy>.<tailnet>.ts.net
tailscale serve (trên máy này)
   │
   └──────────────►  http://127.0.0.1:8000
                     Web server (FastAPI)
                       │ đọc / ghi
                     SQLite  results/app.db  (WAL)
                       ▲ ghi tiến độ
                     Runner (tiến trình riêng) → các bước pipeline → worker MCTS theo khung
```

- Web, SQLite và tính toán đều nằm trên máy này; tắt máy là mất web. `tailscale serve` chuyển địa chỉ `*.ts.net` (có HTTPS sẵn) về `127.0.0.1:8000`, chỉ thiết bị trong tailnet của người dùng mở được.
- Một server FastAPI phục vụ cả giao diện lẫn API.
- **[đề xuất]** Giao diện render phía server (Jinja2 + HTMX), biểu đồ bằng uPlot hoặc Chart.js nạp sẵn trong `web/static/`. Không cần Node / bước build; cập nhật trực tiếp bằng Server-Sent Events (hoặc hỏi lại mỗi 2 giây nếu SSE gặp lỗi).
- **Runner là tiến trình riêng**, web chỉ tạo bản ghi lượt chạy rồi khởi động runner. Khởi động lại web không giết lượt đang chạy. Mỗi lúc chỉ một lượt chạy (MCTS đã dùng hết CPU với 7 khung).
- Thư viện thêm vào `requirements.in`: `fastapi`, `uvicorn`, `jinja2`. Tailscale đã cài sẵn trên máy (người dùng xác nhận 2026-10-28).

## 3. Các bước pipeline mà web hiển thị

Đọc từ code hiện tại (`main.py`, `RunMCTS.process_timeframe`, `MCTSEngine.run_search_from_blueprint`) và kế hoạch (`docs/ROADMAP.md`, `docs/PLANTED_SIGNAL.md`, proposal):

| Bước | Đơn vị việc | "Xong bao nhiêu" đo bằng | Có trong code |
|---|---|---|---|
| 1. Sinh blueprint (LLM) | một ý tưởng | ý tưởng hợp lệ / yêu cầu, số lần tự sửa, số bị loại khi biên dịch | ✅ `generate` |
| 2. Biên dịch | một blueprint × khung | qua / lỗi (kèm lỗi) | ✅ trong `mcts` |
| 3. Tìm MCTS | một blueprint × khung × cửa sổ × seed | vòng lặp đã chạy / ngân sách, reward tốt nhất, số ứng viên đã chấm, tỷ lệ bị −10, lỗi hay gặp, lý do dừng (hết vòng / patience / entropy) | ✅ `mcts` |
| 4. Chọn và gộp | một (khung, cửa sổ, seed) | số ứng viên reward > 0; top-1 hôm nay, top-5 trọng số đều sau này | 🔧 top-1 có, top-5 chưa |
| 5. Kiểm định mô tả HMM | một alpha đã chọn | qua tầng 1/2/3, lý do | ✅ |
| 6. Lưu danh mục | một alpha | đã lưu, đường dẫn code / CSV | ✅ |
| 7. Đánh giá ngoài mẫu | một (cửa sổ, cấu hình, seed) | Sharpe OOS | ⛔ chưa có (walk-forward) |

"Alpha" trên màn hình luôn ghi rõ là loại nào, vì ba con số khác nhau: **đã chấm** (mọi ứng viên), **qua cổng** (reward > −10), **đã chọn** (vào danh mục).

**Bắt đầu từ bước nào:**
- Từ bước 1: sinh bộ blueprint mới.
- Từ bước 3: chọn một **bộ blueprint đã đóng băng** có sẵn trong DB (đúng như việc 3 và walk-forward cần).
- Từ bước 4–5: chọn lại / kiểm định lại từ ứng viên đã lưu của một lượt cũ (ví dụ đổi top-1 thành top-5 mà không tìm lại).
- **Chạy tiếp lượt dở:** bỏ qua các việc đã xong; việc MCTS đang dở thì chạy lại từ đầu việc đó (không lưu được cây MCTS giữa chừng).

**Loại thí nghiệm** (chọn khi khởi chạy, mở dần theo ROADMAP): pipeline thường (có ngay) → bài cài tín hiệu (việc 3) → walk-forward 11 cửa sổ × 7 cấu hình × 5 seed → placebo K = 19 → SPA / DSR.

## 4. Thay đổi cần trong lõi (trước khi có web)

Hiện tiến độ chỉ có `print()`, và đầu vào là thư mục `results/ideas/` bị chuyển tệp sang `processed/` khi chạy. Cần:

1. **Callback tiến độ, không bắt buộc:** `run_search_from_blueprint(..., on_progress=None, should_stop=None)`. Gọi mỗi khoảng ~2 giây (không phải mỗi vòng) với: vòng hiện tại, reward tốt nhất, số lần chấm, số lỗi, số bị −10. `None` thì như hôm nay, nên CLI và test không đổi.
2. **Dừng nhẹ nhàng:** `should_stop()` được hỏi cùng nhịp đó; trả True thì thoát vòng lặp, ghi lý do dừng là "người dùng dừng".
3. **Đầu vào blueprint là danh sách**, không phải thư mục: `process_timeframe` nhận danh sách blueprint. CLI vẫn đọc thư mục rồi truyền danh sách vào, nên hành vi CLI giữ nguyên; runner của web lấy từ DB và không chuyển tệp.
4. **Ghi số bị −10 và lý do** (Calmar < 1.1 hay < 15 lệnh) vào `MCTSEngine` — cũng chính là số đo mà `docs/PLANTED_SIGNAL.md` mục 5 cần.
5. Mỗi lượt chạy lưu ảnh chụp cấu hình (`AppConfig` liên quan, tham số, seed, commit git, dấu vân tay dữ liệu) để tái lập trong luận văn.

Test bắt buộc: cùng seed, có và không có callback ra cùng leaderboard; `should_stop` trả True thì dừng trong một nhịp; CLI đọc thư mục vẫn cho cùng kết quả như trước khi tách.

## 5. Cơ sở dữ liệu SQLite (bản nháp, chuẩn hoá lại khi bắt đầu code)

Tệp `results/app.db`, chế độ WAL, `busy_timeout` để các worker cùng ghi. Chuỗi thời gian lớn (đường vốn, vị thế từng bar) vẫn để ở CSV, DB chỉ giữ đường dẫn.

| Bảng | Khoá | Cột chính | Phụ thuộc vào |
|---|---|---|---|
| `blueprint_set` | id | name, model, prompt_hash, created_at, frozen | một lần sinh |
| `blueprint` | id | set_id, name, timeframe, expression, raw_json | một ý tưởng LLM trả về |
| `experiment` | id | kind (pipeline / planted / walk_forward / placebo), name, config_json, created_at | một thiết kế thí nghiệm |
| `data_window` | id | experiment_id, search_start, search_end, eval_start, eval_end | một cửa sổ của thí nghiệm |
| `run` | id | experiment_id, start_stage, status, started_at, finished_at, git_commit, data_fingerprint, pid | một lần bấm chạy (chạy tiếp = lượt mới cùng thí nghiệm) |
| `search_task` | id | run_id, blueprint_id, window_id, seed, iterations_budget, status, stop_reason, started_at, finished_at, error | một việc MCTS; khung lấy từ blueprint, không lặp lại |
| `search_progress` | (task_id, iteration) | best_reward, n_evaluated, n_failed, n_gated, elapsed_s | một nhịp ghi tiến độ |
| `candidate` | id | task_id, expression, template, direction, reward | một ứng viên trong leaderboard |
| `candidate_param` | (candidate_id, name) | value | tham số template (window, z_score, ngưỡng) — tách ra vì mỗi template có bộ tham số khác, để chung một bảng thì phải bỏ trống cột |
| `candidate_metric` | (candidate_id, segment, name) | value | chỉ số trên đoạn tìm / đoạn đánh giá |
| `selection` | (run_id, window_id, seed, candidate_id) | rank, weight | việc chọn top-k |
| `validation` | (candidate_id, kind) | passed, tier_failed, reason, details_json | kết quả HMM |
| `artifact` | id | run_id, candidate_id, kind (code / equity / positions), path | tệp trên đĩa |
| `log_line` | id | run_id, created_at, level, source, message | stdout của runner |

Tiến độ "bước đang chạy" và "xong bao nhiêu" **tính ra từ** `search_task` / `candidate`, không lưu thành cột riêng, để không có hai nơi chứa một sự thật.

Dữ liệu cũ (`results/portfolio_summary.json`, chiến lược thế hệ đầu) không nhập vào DB: tính theo công thức cũ, sẽ làm lẫn số.

## 6. Các trang

1. **Tổng quan** — lượt đang chạy: thanh tiến độ theo bước, bước hiện tại, ước thời gian còn lại, ba con số alpha (đã chấm / qua cổng / đã chọn); nút Dừng; danh sách lượt gần đây.
2. **Khởi chạy** — chọn loại thí nghiệm, bước bắt đầu, bộ blueprint, khung, model, số ý tưởng, vòng lặp, patience, seed. Trước khi bấm chạy hiện số việc sẽ tạo và ước thời gian. Ô `--retrain-hmm` có cảnh báo (dựng cache ~13 GB, lâu).
3. **Chi tiết lượt chạy** — dòng thời gian các bước; lưới khung × blueprint tô màu theo trạng thái; bấm một ô ra biểu đồ reward tốt nhất theo vòng, tỷ lệ −10, lỗi hay gặp, lý do dừng; đuôi log.
4. **Bộ blueprint** — danh sách bộ, từng blueprint, biên dịch được không, bộ nào đã đóng băng, đã dùng ở lượt nào; đóng băng một bộ.
5. **Ứng viên và alpha** — bảng lọc theo khung / template / reward; chi tiết: công thức, tham số, chỉ số đoạn tìm và đoạn đánh giá, đường vốn so với mua-và-giữ, vị thế, kết quả HMM từng tầng, code xuất ra.
6. **Thí nghiệm luận văn** (mở khi từng phần có code) — bài cài tín hiệu: bảng độ mạnh × tỷ lệ tìm lại + điểm "đáp án"; walk-forward: 11 cửa sổ × 7 cấu hình; placebo: biểu đồ phân bố 19 lần so với kết quả thật; SPA / DSR.
7. **Dữ liệu và hệ thống** — tệp dữ liệu từng khung, khoảng ngày, số ngày thiếu (nợ 126 ngày ở khung phút), cache HMM có / chưa, Ollama có đang chạy, mô hình nào có.

Giao diện phải dùng được trên điện thoại (chủ yếu để xem).

## 7. An toàn

Web có nút khởi chạy tính toán trên máy này, nên chỉ được mở trong tailnet:
- Server chỉ nghe ở `127.0.0.1`, không nghe `0.0.0.0`; đường duy nhất từ máy khác vào là `tailscale serve`. Máy khác trong Wi-Fi chung không vào được.
- ⛔ Không bật `tailscale funnel` (đưa ra Internet công khai).
- Không có ô nhập lệnh hay biểu thức tự do: mọi tham số đi qua danh sách cho phép và kiểu số có giới hạn.
- Không làm trang đăng nhập riêng: tailnet chỉ có thiết bị của người dùng.

## 8. Thứ tự làm

| Giai đoạn | Việc | Xong khi |
|---|---|---|
| W0 | Chốt mục 9 | ROADMAP ghi quyết định |
| W1 | Móc tiến độ / dừng / danh sách blueprint / đếm −10 vào lõi (mục 4, điểm 1–4; điểm 5 làm ở W2 cùng bảng `run`) | test mục 4 xanh, CLI ra cùng kết quả |
| W2 | Schema SQLite + bộ ghi + runner chạy được từ dòng lệnh | một lượt `mcts` thật ghi đủ bảng, đo được tốc độ chậm đi bao nhiêu |
| W3 | Web chỉ xem: trang 1, 3, 5 | xem được lượt đang chạy trên `127.0.0.1` |
| W4 | Khởi chạy / dừng / chạy tiếp: trang 2, 4 | khởi chạy từ bước 3 với bộ đã đóng băng, dừng giữa chừng, chạy tiếp |
| W5 | `tailscale serve` tới cổng 8000 | mở được `https://<tên-máy>.<tailnet>.ts.net` từ điện thoại; máy ngoài tailnet và máy cùng Wi-Fi không mở được |
| W6 | Trang 6, 7 theo tiến độ luận văn | mỗi thí nghiệm có trang khi có code |

Code giao cho agent `coder` từng giai đoạn, kiểm xong mới sang giai đoạn sau.

## 9. Câu chờ người dùng quyết

- ✅ **Thứ tự so với luận văn:** W1 làm ngay cùng việc 3 (có ích cho cả hai); W2–W5 sau khi việc 3 có kết quả, để web không ăn thời gian của RQ (người dùng chốt 2026-10-28).
- ✅ **Cách mở từ xa:** Tailscale, không Cloudflare, không tên miền (người dùng chốt 2026-10-28).
- ✅ **Khởi chạy từ xa:** từ thiết bị trong tailnet được cả xem, khởi chạy và dừng (người dùng chốt 2026-10-28).
- ✅ **Không nhập dữ liệu cũ** vào DB (mục 5) (người dùng chốt 2026-10-28).
