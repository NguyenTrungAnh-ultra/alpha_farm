# Web điều khiển và theo dõi

Thiết kế như đang dùng. Trạng thái: [PLAN](../PLAN.md) việc 14. Quyết định: [DECISIONS](../DECISIONS.md#web). Bản trước khi tách: [log/2026-10_WEB_DASHBOARD](../log/2026-10_WEB_DASHBOARD.md).

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
- Thư viện thêm vào `requirements.in`: `fastapi`, `uvicorn`, `jinja2`, `psutil` (CPU / RAM). GPU đọc bằng `nvidia-smi --query-gpu=... --format=csv` (máy có RTX 5060 8 GB, Ollama chạy trên đó), không thêm thư viện.

## 3. Các bước pipeline mà web hiển thị

Đọc từ code hiện tại (`main.py`, `RunMCTS.process_timeframe`, `MCTSEngine.run_search_from_blueprint`), [PLAN](../PLAN.md), [PLANTED_SIGNAL](PLANTED_SIGNAL.md) và proposal:

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

**Loại thí nghiệm** (chọn khi khởi chạy, mở dần theo [PLAN](../PLAN.md)): pipeline thường (có ngay) → bài cài tín hiệu (việc 3) → walk-forward 11 cửa sổ × 7 cấu hình × 5 seed → placebo K = 19 → SPA / DSR.

## 4. Thay đổi cần trong lõi (trước khi có web)

Hiện tiến độ chỉ có `print()`, và đầu vào là thư mục `results/ideas/` bị chuyển tệp sang `processed/` khi chạy. Cần:

1. **Callback tiến độ, không bắt buộc:** `run_search_from_blueprint(..., on_progress=None, should_stop=None)`. Gọi mỗi khoảng ~2 giây (không phải mỗi vòng) với: vòng hiện tại, reward tốt nhất, số lần chấm, số lỗi, số bị −10. `None` thì như hôm nay, nên CLI và test không đổi.
2. **Dừng nhẹ nhàng:** `should_stop()` được hỏi cùng nhịp đó; trả True thì thoát vòng lặp, ghi lý do dừng là "người dùng dừng".
3. **Đầu vào blueprint là danh sách**, không phải thư mục: `process_timeframe` nhận danh sách blueprint. CLI vẫn đọc thư mục rồi truyền danh sách vào, nên hành vi CLI giữ nguyên; runner của web lấy từ DB và không chuyển tệp.
4. **Ghi số bị −10 và lý do** (Calmar < 1.1 hay < 15 lệnh) vào `MCTSEngine` — cũng là số đo bài cài tín hiệu cần.
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
| `system_sample` | sampled_at | cpu_pct, ram_used_mb, ram_total_mb, gpu_pct, vram_used_mb, vram_total_mb | một lần đo máy (mỗi 5 giây khi web chạy); `run_id` không lưu, lượt chạy suy ra từ khoảng thời gian của `run`. Giữ 7 ngày rồi xoá |

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
8. **Tài nguyên máy** — CPU tổng và theo từng nhân, RAM, GPU % và VRAM, đồ thị 1 giờ gần nhất; ổ đĩa còn trống (cache HMM có thể tới hàng GB). Ô nhỏ CPU / RAM / GPU hiện cả ở trang Tổng quan, và đồ thị tài nguyên nằm trong trang Chi tiết lượt chạy theo khoảng thời gian của lượt đó. Không có GPU / `nvidia-smi` lỗi thì hiện "không đọc được", không làm hỏng trang.

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
| W3a ✅ | Web chỉ xem, đọc thẳng tệp kết quả (chưa có DB): trang bài cài tín hiệu (mục 10), trang 8 tài nguyên máy | mở `http://127.0.0.1:8000`, thấy bảng + hình của `results/planted*/`, thấy tiến độ lượt `search` đang chạy và CPU / RAM / GPU |
| W3b | Web luận văn (mục 10) | mọi trang ở mục 10 mở được; trang `/results/planted` chỉ đọc `planted_window1` |
| W1 ✅ | Móc tiến độ / dừng / danh sách blueprint / đếm −10 vào lõi (mục 4, điểm 1–4; điểm 5 làm ở W2 cùng bảng `run`) | test mục 4 xanh, CLI ra cùng kết quả |
| W2 | Schema SQLite + bộ ghi + runner chạy được từ dòng lệnh | một lượt `mcts` thật ghi đủ bảng, đo được tốc độ chậm đi bao nhiêu |
| W3 | Web chỉ xem: trang 1, 3, 5, 8 | xem được lượt đang chạy trên `127.0.0.1` |
| W4 | Khởi chạy / dừng / chạy tiếp: trang 2, 4 | khởi chạy từ bước 3 với bộ đã đóng băng, dừng giữa chừng, chạy tiếp |
| W5 | `tailscale serve` tới cổng 8000 | mở được `https://<tên-máy>.<tailnet>.ts.net` từ điện thoại; máy ngoài tailnet và máy cùng Wi-Fi không mở được |
| W6 | Trang 6, 7 theo tiến độ luận văn | mỗi thí nghiệm có trang khi có code |

Code giao cho agent `coder` từng giai đoạn, kiểm xong mới sang giai đoạn sau.

## 10. Web luận văn (W3b, thay trang W3a)

Web đọc như chính bài luận: mỗi trang là một chương, mỗi bảng / hình có số thứ tự, chú thích nói **trả lời câu hỏi nào** (RQ1 / RQ2) và một câu đọc kết quả. Chỉ hiện cấu hình đã chốt cho luận văn; ⛔ so các phương án đã thử trong quá trình làm (thư mục cũ, reward mode cũ, ngữ pháp cũ), ⛔ bảng thô nội bộ.

**Vấn đề của trang W3a (soát 2026-10-30):**
- Không nói bài cài tín hiệu trả lời RQ2, không giải thích A là gì, "tìm lại gần / đúng" nghĩa là gì.
- Liệt kê bốn thư mục (`planted`, `planted_run2_sharpe`, `planted_run3`, `planted_window1`) với reward `soft` / `sharpe` và hình so giữa chúng: đó là quá trình chọn phương án, không phải kết quả.
- Bảng oracle thô (`reward_gated`, `z_soft`, `calmar`, seed in `1.0000` …) hiện ra trang.
- "20 / 15 lượt": số lượt dự kiến đọc từ dòng đầu `search.log`, sai khi chạy thêm seed.
- Chữ trạng thái nội bộ ("có search.log, chưa đủ lượt…").
- Trang gốc `/` là bài cài tín hiệu, không có trang tổng quan tiến độ luận văn.
- Ghi chú ô `rq2_planted` trên `/pipeline` còn nhắc "lần chạy 1–3 (ngữ pháp cũ)".
- Kết quả so vị thế (`positions_vs_a.json`) chưa có trên web.
- Trang "Một bộ dữ liệu" không vẽ được đường vốn top-5 vì `runs.csv` không lưu tham số template.

**Cấu trúc:**

| Đường dẫn | Chương | Nội dung |
|---|---|---|
| `/` | Tổng quan | tên đề tài, câu hỏi chính, RQ1 / RQ2; bảng tiến độ: mỗi chương / mỗi bảng-hình một dòng, trạng thái ✅ / 🔧 / chưa có |
| `/method` | Phương pháp | sơ đồ luồng chính (trang `/pipeline` hiện có), bảng cửa sổ walk-forward, bộ blueprint đã đóng băng |
| `/data` | Dữ liệu | VN30F1M 60m 2018-08 → 2025-12, số bar từng đoạn, ghi chú dữ liệu |
| `/results/planted` | Kết quả — RQ2, kiểm soát dương | xem dưới |
| `/results/placebo` | Kết quả — RQ2, kiểm soát âm | đọc `results/walkforward/llm_mcts/summary.csv`: phân bố Sharpe của K bộ placebo (chấm từng bộ, vạch Sharpe placebo lớn nhất), bảng từng bộ, câu đọc nói Sharpe thật phải vượt Sharpe placebo lớn nhất để p = 1/(K+1). p = (1 + số bộ có Sharpe ≥ thật) / (K + 1), tính từ dữ liệu; chưa có dòng `real` thì p hiện "chưa có, chờ lần chạy thật" |
| `/results/rq1` | Kết quả — RQ1 | như trên |
| `/results/walkforward` | Kết quả — chuỗi ngoài mẫu | như trên |
| `/system` | Công cụ (ngoài luận văn) | tài nguyên máy, tiến độ lượt chạy đang chạy |

**Trang `/results/planted`** (nguồn duy nhất: thư mục kết quả luận văn, hằng `THESIS_PLANTED_DIR = 'planted_window1'` trong `web/`):
1. Đoạn mở: câu hỏi (quy trình có tìm lại một tín hiệu biết trước không → RQ2), cách làm trong ba câu (xáo lợi suất, cài A với IC biết trước, chạy đúng quy trình luận văn), A viết bằng lời và bằng công thức.
2. Bảng: IC mục tiêu · số seed · IC đo được (đoạn tìm, đoạn đánh giá) · tìm lại gần · tìm lại đúng · Sharpe ngoài mẫu. Chú thích định nghĩa "tìm lại gần / đúng".
3. Hình: tỷ lệ tìm lại gần theo IC (khoảng tin cậy 95% Wilson vẽ làm thanh sai số). Ngưỡng phát hiện = mức IC > 0 thấp nhất có p < 0.05 trong kiểm định chính xác Fisher một phía (`scipy.stats.fisher_exact`, alternative `greater`) so tỷ lệ tìm lại gần với IC 0; p có cột riêng ở Bảng 4.1 (IC 0 hiện "—"), ngưỡng và p hiện trong ô "Chỉ số chính" và câu đọc. Không mức nào đạt thì trang nói chưa xác định được ngưỡng.
4. Hình: tương quan của ứng viên gần A nhất ở mỗi seed theo IC (chấm từng seed, vạch mốc 0.7).
5. Bảng / hình: tương quan vị thế tốt nhất trong top-5 với A, theo IC, kèm mức nhiễu (IC 0) — từ `positions_vs_a.json` nếu có.
6. Bảng từng seed (gọn): IC · seed · công thức gần A nhất · tương quan · tìm lại gần / đúng · Sharpe ngoài mẫu.
7. Liên kết tới trang minh hoạ một bộ dữ liệu (giữ trang hiện có, đổi tiêu đề thành "Minh hoạ: cài tín hiệu làm gì với giá", bỏ chọn thư mục).

**Vai trò của chỉ số** (người dùng yêu cầu 2026-10-30):
- Mỗi trang chương mở bằng ô **"Chỉ số chính"**: tên chỉ số trả lời trực tiếp câu hỏi của chương, nó đo gì, đọc thế nào, giá trị hiện tại (hoặc "chưa có").
- Mỗi bảng / hình mang một nhãn vai trò: **chính** (trả lời câu hỏi), **phụ** (bổ sung, không dùng để kết luận một mình), **chẩn đoán** (giải thích vì sao, không phải kết quả).
- Mỗi chỉ số có một định nghĩa ngắn "đo gì" (hiện khi rê chuột lên tiêu đề cột, và trong danh sách chỉ số cuối trang). Định nghĩa nằm một chỗ trong module nội dung, mọi trang dùng chung.

| Chương | Chỉ số chính | Phụ | Chẩn đoán |
|---|---|---|---|
| RQ2 — bài cài tín hiệu | tỷ lệ tìm lại gần theo IC (Bảng 4.1, Hình 4.1) | tìm lại đúng; tương quan vị thế top-5 với A; Sharpe ngoài mẫu 6 tháng (rất nhiễu, không dùng để kết luận) | ứng viên gần A nhất trong mọi ứng viên (đo MCTS có chạm tới A không) |
| RQ2 — placebo | p-value: tỷ lệ bộ placebo có Sharpe ngoài mẫu ≥ lần thật | phân bố Sharpe 19 bộ placebo | — |
| RQ1 | Sharpe năm của chuỗi ngoài mẫu từng cấu hình | IC, Calmar, vòng quay | — |
| Chuỗi ngoài mẫu | Sharpe năm của chuỗi 2022-07 → 2025-12 | Sharpe từng cửa sổ, sụt giảm lớn nhất | — |

Hình "ứng viên gần A nhất" là chẩn đoán: tô khác màu điểm nằm trong top-5 và điểm không vào top-5; câu đọc nói "MCTS đã chạm tới A ở k/n seed", không nói "tìm thấy".

**Nội dung chữ** (đoạn mở, chú thích, câu đọc kết quả, trạng thái từng chương) nằm trong một module Python của `web/` như `web/pipeline.py`; số liệu luôn tính từ tệp kết quả. Web không đọc `docs/`.

**Giữ nguyên:** chỉ đọc, nghe `127.0.0.1`, không đổi phép tính; FastAPI + Jinja2, Chart.js như hiện có.
