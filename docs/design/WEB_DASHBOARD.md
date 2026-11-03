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
| W3b | Web luận văn (mục 10) | mọi trang ở mục 10 mở được; trang `/results/planted` chỉ đọc `planted_rq1` |
| W1 ✅ | Móc tiến độ / dừng / danh sách blueprint / đếm −10 vào lõi (mục 4, điểm 1–4; điểm 5 làm ở W2 cùng bảng `run`) | test mục 4 xanh, CLI ra cùng kết quả |
| W2 | Schema SQLite + bộ ghi + runner chạy được từ dòng lệnh | một lượt `mcts` thật ghi đủ bảng, đo được tốc độ chậm đi bao nhiêu |
| W3 | Web chỉ xem: trang 1, 3, 5, 8 | xem được lượt đang chạy trên `127.0.0.1` |
| W4 | Khởi chạy / dừng / chạy tiếp: trang 2, 4 | khởi chạy từ bước 3 với bộ đã đóng băng, dừng giữa chừng, chạy tiếp |
| W5 | `tailscale serve` tới cổng 8000 | mở được `https://<tên-máy>.<tailnet>.ts.net` từ điện thoại; máy ngoài tailnet và máy cùng Wi-Fi không mở được |
| W6 | Trang 6, 7 theo tiến độ luận văn | mỗi thí nghiệm có trang khi có code |

Code giao cho agent `coder` từng giai đoạn, kiểm xong mới sang giai đoạn sau.

## 10. Web luận văn (W3b, thay trang W3a)

Web đọc như chính bài luận: mỗi trang là một chương, mỗi bảng / hình có số thứ tự, chú thích nói **trả lời câu hỏi nào** (RQ1 / RQ2) và một câu đọc kết quả. Chỉ hiện hệ thống RQ1 (LLM + MCTS có vòng phản hồi) và cấu hình đã chốt cho luận văn; ⛔ so các phương án đã thử trong quá trình làm (thư mục cũ, hệ thống sinh một lần, reward mode cũ, ngữ pháp cũ), ⛔ bảng thô nội bộ. Kết quả của hệ thống cũ (`results/planted_window1/`, `results/walkforward/oneshot_placebo/`) là lịch sử, web không đọc.

Mục nào thiếu tệp kết quả hiện trạng thái chờ (chữ "chưa có" kèm lệnh cần chạy), không lỗi; trang vẫn dựng được khi chỉ có `planted_formulas.json` và `coverage.json`.

**Cấu trúc:**

| Đường dẫn | Chương | Nội dung |
|---|---|---|
| `/` | Tổng quan | tên đề tài, câu hỏi chính, RQ1 / RQ2; bảng tiến độ: mỗi chương / mỗi bảng-hình một dòng (registry `CHAPTERS` / `ITEMS` trong `web/thesis.py`), trạng thái ✅ / 🔧 / chưa có |
| `/method` | Phương pháp | sơ đồ luồng chính (Hình 3.1; vẽ vòng phản hồi: a1 giai đoạn A → a2 phản hồi LLM → a3 giai đoạn B → b → c → d, mũi tên vòng d → a1; trạng thái ba ô so sánh suy ra từ tệp kết quả, xem dưới), cửa sổ walk-forward (Hình 3.2), Bảng 3.1 bộ blueprint RQ1 đóng băng (20 khung, số cách điền, độ phủ toán tử 16/19), Bảng 3.2 các cấu hình so sánh, Bảng 3.3 vòng phản hồi và mốc ngân sách, Bảng 3.4 kích thước không gian tìm kiếm (toàn ngữ pháp ≈ 1.9 × 10⁴¹ so với bộ ≈ 2.2 × 10¹⁴; tính bằng `GrammarSize`, không gõ cứng) |
| `/data` | Dữ liệu | VN30F1M 60m 2018-08 → 2025-12, số bar từng đoạn, ghi chú dữ liệu |
| `/results/planted` | Kết quả: bài cài tín hiệu (RQ2 kiểm soát dương; cũng là dữ liệu của phép so chính RQ1) | xem dưới |
| `/results/placebo` | Kết quả: RQ2, kiểm soát âm | đọc `results/walkforward/llm_mcts/summary.csv`: phân bố Sharpe của K bộ placebo (chấm từng bộ, vạch Sharpe placebo lớn nhất), bảng từng bộ, câu đọc nói Sharpe thật phải vượt Sharpe placebo lớn nhất để p = 1/(K+1). p = (1 + số bộ có Sharpe ≥ thật) / (K + 1), tính từ dữ liệu, "thật" = dòng `real_seed1` (MCTS seed 1, cùng cách đo với bộ placebo; vạch "lần chạy thật (seed 1)" trên biểu đồ); Sharpe trung bình 5 seed (dòng `real_mean`) hiện thêm trong câu đọc, ghi rõ chỉ mô tả, không có p; chưa có dòng `real_seed1` thì p hiện "chưa có, chờ lần chạy thật"; chưa có thư mục thì hiện trạng thái chờ |
| `/results/rq1` | Kết quả: RQ1 | xem dưới |
| `/results/walkforward` | Kết quả: chuỗi ngoài mẫu | chưa có kết quả (cần đóng băng rồi chạy thật) |
| `/thesis` | Luận văn (PDF) | kích thước và giờ sửa của hai tệp `docs/thesis/Thesis.pdf` (bản chính) và `docs/thesis/Thesis_noDSR.pdf` (bản không DSR), khung `<object>` nhúng bản chính (85vh), nút "Mở toàn màn hình" (tab mới, cách chắc chắn trên điện thoại) và "Tải về"; thiếu tệp thì hiện "chưa có bản PDF". Thư mục lấy từ `app.state.thesis_dir` (tham số `thesis_dir` của `create_app`, mặc định `docs/thesis/`) |
| `/thesis/pdf?version=main\|nodsr` | (tệp) | `FileResponse`, `application/pdf`, `Content-Disposition: inline`, `Cache-Control: no-cache` |
| `/thesis/download?version=main\|nodsr` | (tệp) | như trên nhưng `attachment`, tên `NguyenTrungAnh_Thesis.pdf` / `NguyenTrungAnh_Thesis_noDSR.pdf`. Chỉ hai tệp cố định qua từ điển `thesis.PDF_VERSIONS`; `version` lạ hoặc tệp thiếu → 404, không nhận đường dẫn từ người dùng |
| `/system` | Công cụ (ngoài luận văn) | tài nguyên máy, tiến độ lượt chạy đang chạy |

**Trang `/results/planted`** (nguồn duy nhất: `results/planted_rq1/`, hằng `THESIS_PLANTED_DIR` trong `web/planted.py`):
1. Đoạn mở: câu hỏi (quy trình có tìm lại một tín hiệu biết trước không → RQ2; cùng bài này đo phép so chính của RQ1), cách làm trong ba câu (xáo lợi suất, cài A với IC biết trước, chạy đúng quy trình luận văn), định nghĩa "tìm lại gần".
2. Bảng 4.1: bốn tín hiệu A: loại (kinh điển / lạ), số toán tử, biểu thức, độ đông (tỷ lệ công thức ngẫu nhiên gần A) và p ADF, từ `planted_formulas.json`.
3. Bảng 4.2 (chính): ngưỡng phát hiện theo A của LLM + MCTS ở ngân sách 100.000, từ `detection_thresholds.csv` = mức IC > 0 thấp nhất có p < 0.05 trong kiểm định chính xác Fisher một phía (`Statistics.fisher_p_greater`, `Statistics.detection_threshold`) so tỷ lệ tìm lại gần với IC 0; kèm số seed tìm lại gần theo IC. Không mức nào đạt thì ghi "chưa xác định". Số seed mỗi ô trong phần đọc là `n_runs` lớn nhất của LLM + MCTS trong `summary.csv` (`planted.seeds_per_cell`), không gõ cứng.
4. Bảng 4.3 (phụ): tỷ lệ tìm lại gần theo A × IC kèm khoảng Wilson 95% và p Fisher một phía so với IC 0 (tính lại từ số đếm của `summary.csv`); Hình 4.1 (phụ): cùng số liệu, mỗi A một ô, Wilson vẽ làm dải.
5. Liên kết tới trang minh hoạ một bộ dữ liệu (chọn A, IC, seed; cần `runs.csv` và `calibration.json`).

**Trang `/results/rq1`** (nguồn: `results/planted_rq1/`, `results/walkforward/comparison.csv`):
1. Đoạn mở: câu hỏi (LLM đưa MCTS tới tín hiệu sớm hơn hay chặn đường), thiết kế trong ba câu, phép so chính duy nhất.
2. Bảng 4.4 (chính): bốn phép Fisher hai phía chỉnh Holm, LLM + MCTS với MCTS không LLM ở IC 0.1, gộp theo loại A (kinh điển, lạ) tại mốc 50.000 và 100.000, từ `primary_tests.csv`.
3. Hình 4.3 (phụ): tỷ lệ tìm lại gần theo ngân sách (10.000 … 100.000) cho từng cấu hình, mỗi A một ô, ở IC 0.1, dải Wilson; đường dọc ở 50.000 ghi "hết giai đoạn A, trước phản hồi".
4. Bảng 4.5 (chẩn đoán): A trong hay ngoài vùng của bộ blueprint ban đầu và số cách điền của blueprint nhỏ nhất chứa A, từ `coverage.json`.
5. Bảng 4.6 (phụ): trung vị số vòng và thời gian tới lần đầu chạm A theo cấu hình × A, kèm số lượt đã chạm / số lượt, từ `first_touch.csv`.
6. Bảng 4.7 (phụ, mô tả): Sharpe ngoài mẫu từng cấu hình, chênh so với LLM + MCTS kèm khoảng tin cậy bootstrap và ρ, từ `comparison.csv`; không có p.
7. Một dòng đọc sức khoẻ vòng phản hồi (đầu trang, dưới phần thiết kế): số lượt LLM + MCTS, số lượt quay về bộ blueprint ban đầu kèm lý do, số lượt phải hỏi lại. Tính bằng `SearchConfigs.summarize_feedback` / `feedback_records` trên cột `feedback` của `runs.csv` (cùng số mà `rq1 summary` in ra; `rq1.read_feedback`); thiếu tệp hoặc cột thì không hiện dòng. Số seed trong phần thiết kế cũng đọc từ `summary.csv`.

**Trang `/results/placebo`** có cùng dòng sức khoẻ vòng phản hồi, tính trên các dòng `mode = placebo` của `results/walkforward/llm_mcts/runs.csv` (`placebo.read_feedback`, khoá `WalkForward.RUN_KEY`).

**Trạng thái ô Hình 3.1:** ô tĩnh giữ trạng thái viết trong `NODES`; ba ô so sánh lấy từ cùng phép kiểm tệp của `availability()` (`pipeline.derived_states`): bài cài tín hiệu = Xong khi có `detection_thresholds.csv`; RQ1 = Đang làm khi có `primary_tests.csv` mà chưa có `comparison.csv`, Xong khi có cả hai; placebo = Đang làm khi có các bộ placebo, Xong khi có thêm dòng `real_seed1` (khoá `placebo_real`). Chưa có tệp nào thì Chưa làm.

**Vai trò của chỉ số** (người dùng yêu cầu 2026-10-30):
- Mỗi trang chương mở bằng ô **"Chỉ số chính"**: tên chỉ số trả lời trực tiếp câu hỏi của chương, nó đo gì, đọc thế nào, giá trị hiện tại (hoặc "chưa có").
- Mỗi bảng / hình mang một nhãn vai trò: **chính** (trả lời câu hỏi), **phụ** (bổ sung, không dùng để kết luận một mình), **chẩn đoán** (giải thích vì sao, không phải kết quả).
- Mỗi chỉ số có một định nghĩa ngắn "đo gì" (hiện khi rê chuột lên tiêu đề cột, và trong danh sách chỉ số cuối trang). Định nghĩa nằm một chỗ trong module nội dung, mọi trang dùng chung.

| Chương | Chỉ số chính | Phụ | Chẩn đoán |
|---|---|---|---|
| RQ2: bài cài tín hiệu | ngưỡng phát hiện theo A của LLM + MCTS ở 100.000 (Bảng 4.2) | tỷ lệ tìm lại gần theo A × IC kèm Wilson và p Fisher (Bảng 4.3, Hình 4.1) | độ đông và p ADF của A (Bảng 4.1) |
| RQ2: placebo | p-value: tỷ lệ bộ placebo có Sharpe ngoài mẫu ≥ lần thật | phân bố Sharpe các bộ placebo | — |
| RQ1 | bốn p Fisher hai phía chỉnh Holm (Bảng 4.4) | tỷ lệ tìm lại gần theo ngân sách (Hình 4.3); lần đầu chạm A (Bảng 4.6); Sharpe walk-forward và chênh so với LLM + MCTS (Bảng 4.7) | A trong / ngoài vùng blueprint và số cách điền (Bảng 4.5) |
| Chuỗi ngoài mẫu | Sharpe năm của chuỗi 2022-07 → 2025-12 | Sharpe từng cửa sổ, sụt giảm lớn nhất | — |

**Nội dung chữ** (đoạn mở, chú thích, câu đọc kết quả, trạng thái từng chương) nằm trong một module Python của `web/` như `web/pipeline.py`; số liệu luôn tính từ tệp kết quả. Web không đọc `docs/`.

**Giữ nguyên:** chỉ đọc, nghe `127.0.0.1`, không đổi phép tính; FastAPI + Jinja2, Chart.js như hiện có.
