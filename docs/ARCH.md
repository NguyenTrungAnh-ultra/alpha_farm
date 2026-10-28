# Kiến trúc Alpha Farm (theo code hiện tại)

Mô tả hệ thống **đúng như code đang chạy**. Phần nào đang hỏng thì ghi rõ ⛔. Việc sẽ làm và câu chờ quyết nằm ở `docs/ROADMAP.md`; phương pháp nghiên cứu nằm ở `docs/proposal/thesis_proposal/Thesis_Proposal.pdf`.
Mọi thông số (ngưỡng, phí, ký quỹ, khoảng ngày) lấy từ `utilities/AppConfig.py`; số ghi dưới đây là giá trị lúc soát code.

## 1. Mục tiêu

Tự tìm tín hiệu có hướng (Long / Short / Flat) cho hợp đồng tương lai VN30F1M: LLM đề xuất cấu trúc chiến lược, MCTS hoàn thiện công thức, backtest chấm điểm, bộ kiểm định HMM đánh giá (không loại) ứng viên.

## 2. Thư mục

| Thư mục | Nội dung |
|---|---|
| `core_engine/` | `AlphaPrimitives.py` (9 toán tử `ts_*`), `BacktestEngine.py` (`AlphaBacktestEngine`, `load_data`), `AlphaEngine.py` (`AlphaDataProxy`, `AlphaStrategy`, lớp bọc `AlphaEngine`), `CalculateMetrics.py` (chỉ số), `GenerateReport.py` (bọc lại `compute_metrics`, đổi tên khoá) |
| `strategy_workflows/` | `GenerateStrategies.py`, `SemanticCompiler.py`, `MCTSDimensions.py`, `MCTSEngine.py`, `RunMCTS.py`, `HMMValidation.py`, `PortfolioManager.py` |
| `llm_clients/` | `OllamaClient.py` (qwen3.5 chạy máy, cùng hàm `extract_json`); dự án chỉ dùng LLM local |
| `utilities/` | `AppConfig.py` (cấu hình tập trung), `Prompts.py` (prompt LLM) |
| `data/` | `DNSE_VN30F_{1m,3m,5m,10m,15m,30m,1H}.csv` (13/08/2018 → 31/12/2025); `MCdata/synthetic/{tf}_{khoá}.pkl` (cache đường giá HMM, mỗi tệp một khung + một bộ dữ liệu); `MCdata/synthetic_data.pkl` (cache cũ ~13 GB, không có siêu dữ liệu nên không còn được nạp) |
| `results/` | `ideas/` (blueprint chờ chạy), `ideas/processed/` (đã chạy), `portfolio_summary.json`, `leaderboard.csv`, `mcts_stats.json` |
| `tests/` | pytest; chạy bằng `.venv` (Python 3.12) |

Tệp một dòng "DELETED" còn sót từ đợt bỏ XNOQuant: `core_engine/PlatformEmulator.py`, `core_engine/RestrictedSeries.py`, `strategy_workflows/SubmitStrategies.py`, `utilities/SandboxPrefixer.py`.

## 3. Luồng chạy

`main.py` điều phối: `generate` (tầng 1) → `mcts` (tầng 2 và kiểm định) → `full` (chạy cả hai).

### 3.1 Tầng 1 — LLM sinh blueprint (`GenerateStrategies.py`)

1. Prompt lấy từ `utilities/Prompts.py`; danh sách trường dữ liệu và toán tử trong prompt sinh từ `OPERATOR_REGISTRY` (bỏ các toán tử trong `UNIMPLEMENTED_OPERATORS`), ví dụ mẫu nằm ở `FEW_SHOT_EXAMPLES` và có test biên dịch từng cái. Mô hình chọn bằng `--model` (`ollama-local` mặc định, `ollama-9b`).
2. LLM trả JSON (kiểm bằng Pydantic) có `macro_blueprint`: biểu thức có chỗ trống `?`.
3. `SemanticCompiler` đọc bằng `ast.parse`, đổi tên hàm bịa qua `HALLUCINATION_MAP`, kiểm thứ nguyên. Lỗi ⇒ gửi lại LLM sửa **1 lần**; gọi API thử lại tối đa 5 lần.
4. Hợp lệ ⇒ lưu `results/ideas/<tên>_<khung>.json`.
5. Code đọc "kinh nghiệm" từ `utilities/experience_log.md`. Tệp này **không tồn tại**: `load_experience_log` in một dòng thông báo, trả chuỗi rỗng, và prompt hiện mục kinh nghiệm với chữ "No experience log is available." (không bịa nội dung).

Prompt dặn LLM chọn gốc công thức thuộc nhóm giữ thứ nguyên (`sub`, `ts_mean`…) hoặc BOOLEAN, tránh gốc RATIO (`ts_zscore`, `ts_rank`, `div`…) vì khuôn RATIO đọc nó như dao động 0–100 (ngưỡng 60–80 / 20–40).

### 3.2 Tầng 2 — MCTS (`RunMCTS.py`, `MCTSEngine.py`, `MCTSDimensions.py`)

1. `run_mcts_pipeline` nạp dữ liệu **một lần** cho mỗi khung (`load_data`, điền Volume thiếu = 0), rồi đưa đúng DataFrame đó cho bước HMM (nạp hoặc dựng cache đường giá), cho `MCTSEngine(data=...)` và cho lượt backtest lại ở `process_timeframe`; ba nơi không thể lệch dữ liệu. `MCTSEngine` không truyền `data` thì tự `load_data(timeframe)` như trước.
2. Mỗi khung chạy một tiến trình. Tiến trình nạp vị thế các chiến lược đã có trong `portfolio_summary.json` (dùng để phạt tương quan), rồi lần lượt biên dịch từng blueprint của khung đó và chạy `run_search_from_blueprint`. Blueprint chạy xong — kể cả khi lỗi — bị chuyển sang `ideas/processed/`. `load_ideas(tf)` chỉ đọc (không chuyển tệp) danh sách ý tưởng của một khung. `process_timeframe(..., ideas=None, on_progress=None, should_stop=None, progress_interval_s=2.0)`: khi truyền `ideas` (list dict `name`, `macro_blueprint`) thì tìm kiếm đúng các ý tưởng đó và **không đọc, không chuyển** gì trong `results/ideas/`; khi `None` thì dùng thư mục như trên. Ba callback chuyển tiếp xuống `run_search_from_blueprint`, snapshot được thêm `timeframe` và `idea_name`. Chế độ danh sách **không** kiểm tra trùng tên với portfolio / `results/failed*` (người gọi quyết định chạy gì); chế độ thư mục giữ kiểm tra đó. Khi một tìm kiếm trả `stopped`, cả khung dừng: không tìm các ý tưởng còn lại (ở chế độ thư mục, tệp của chúng không bị chuyển; tệp đang chạy vẫn được chuyển), bỏ qua replay + HMM + commit và trả `(tf, số ứng viên hiện có, 0, [])`.
3. **Ngữ pháp**: mỗi toán tử khai báo thứ nguyên vào/ra (CURRENCY, VOLUME, RATIO, BOOLEAN, ANY); chỉ điền vào chỗ trống những nút hợp thứ nguyên. Toán tử có code sinh: 9 `ts_*`, logic (`greater_than`, `less_than`, `equal`, `and_`, `or_`, `not_`), số học (`add`, `sub`, `mult`, `div`). `crossed`, `crossed_above`, `crossed_below`, `rising`, `falling`, `between` có trong `OPERATOR_REGISTRY` (biên dịch được) nhưng **chưa có code sinh** (`UNIMPLEMENTED_OPERATORS`): MCTS không đề xuất chúng, và blueprint chứa chúng bị `run_search_from_blueprint` từ chối ngay.
   Chỗ trống `?` lấy thứ nguyên từ chữ ký của toán tử cha (hoặc từ thứ nguyên gắn sẵn khi MCTS mở rộng); chỗ BOOLEAN chỉ nhận toán tử trả BOOLEAN. Chỗ vào của `ts_*` không nhận hằng số.
4. **Khuôn vị thế** theo thứ nguyên gốc: NORMALIZED (z-score trượt, ngưỡng θ), RATIO (ngưỡng trên/dưới), BOOLEAN (±w). Tỷ trọng khi chấm điểm `w = 0.2`. Mỗi công thức thử cả hai chiều, giữ chiều tốt hơn.
5. **Cửa sổ** khai báo ở khung 10m (`BASE_PERIODS`, `BASE_WINDOW_SEARCH`) rồi co giãn theo khung. Độ dài cửa sổ của mỗi nút `ts_*` là **một thuộc tính của nút** (`ASTNode.window`), do MCTS chọn trong `scaled_periods` khi mở rộng (một nước đi riêng, như cửa sổ z-score của khuôn NORMALIZED). `ast_to_code` chỉ đọc thuộc tính này; nút `ts_*` chưa có cửa sổ thì chưa là nút kết thúc, và dựng code sẽ báo lỗi. Một nút MCTS ứng với đúng một công thức.
6. **Điểm thưởng**: `R = (0.6·S_calmar + 0.4·S_IC) · (1 − tương quan vị thế lớn nhất)`; IC là tương quan Spearman với lợi suất bar kế tiếp. Hai chế độ (`AppConfig.REWARD_MODE`, tham số `MCTSEngine(reward_mode=...)`, tham số cuối của `process_timeframe`; giá trị khác `gated`/`soft` ⇒ `ValueError`): **`gated`** (mặc định) cho `R = −10` nếu Calmar < 1.1 hoặc < `MIN_TRADES` (15) lệnh; **`soft`** không có cổng: `S_calmar = clip((Calmar − 1.1)/(3.0 − 1.1), 0, 1)` như cũ nhưng `S_calmar = 0` khi < 15 lệnh (phần IC giữ nguyên), nên ứng viên yếu có điểm thấp thay vì −10.
7. **Chọn nút**: UCT với giá trị **lớn nhất** (không phải trung bình), `c = 1.414`. Không còn bộ nhớ chống trùng (FSA) vì R tối đa là 1.0; công thức đã chấm được tra lại từ `cache`.
8. **Dừng sớm**: entropy chuẩn hoá của lượt thăm ở gốc < 0.15, hoặc 5 000 vòng không cải thiện (`patience`); trần mặc định 50 000 vòng.
9. Lấy **đúng 1** ứng viên tốt nhất có R > 0 mỗi khung → backtest lại → kiểm định HMM (mục 3.3, chỉ mô tả: kết quả không loại ứng viên) → `PortfolioManager.evaluate_and_add`. `PortfolioManager` không còn tiêu chí nào: mọi ứng viên được lưu, tương quan chỉ để cảnh báo/báo cáo (`MAX_CORRELATION = 0.5` nằm trong `PortfolioManager.py`). Ứng viên thành công mang khoá `hmm = {passed, tier_failed, reason, details}` (`None` khi thiếu đường giả lập); `passed/tier_failed/reason` được ghi vào mục chiến lược trong `portfolio_summary.json` dưới `hmm`.

**Chấm điểm và nối với backtest** (`evaluate_expression`):
- Công thức được `eval` (không có builtins) với `open_/high/low/close/volume` là `pd.Series` và 9 hàm `ts_*`; kết quả bắt buộc là `pd.Series`. `compute_positions` (một hàm duy nhất) biến alpha thành `pd.Series` vị thế cùng chỉ mục dữ liệu rồi đưa vào `AlphaBacktestEngine.run`.
- Ngoại lệ khi dựng code / `eval` / backtest vẫn cho −10 nhưng **không bị nuốt**: đếm theo "Loại: thông điệp" (`error_counts`), log cảnh báo ở lần đầu, và cuối `run_search_from_blueprint` in số lần chấm, số lần lỗi và các lỗi hay gặp (`error_summary()`). Cả lượt chấm đều lỗi ⇒ log mức ERROR.
- **Cổng cứng được đếm**: một lượt chấm là "bị chặn" (`gated_evaluation_count`) khi không có ngoại lệ và không hướng nào qua cổng (`total_trades < 15` hoặc Calmar dưới ngưỡng). Lý do ghi trong `gate_reasons`: `too_few_trades` nếu cả hai hướng dưới 15 lệnh, ngược lại `low_calmar`. Cache hit không được đếm. Ở chế độ `soft` bộ đếm luôn 0 (không có kết quả −10 do cổng); ngoại lệ vẫn tính vào `failed_evaluations` và cho −10 ở cả hai chế độ. `error_summary()` trả thêm `gated_evaluations`, `gate_reasons`; dòng tổng kết cuối tìm kiếm in cả hai. Số lượt qua cổng = `evaluations − failed_evaluations − gated_evaluations`.
- **Móc quan sát / dừng**: `run_search_from_blueprint(root, n_iterations, on_progress=None, should_stop=None, progress_interval_s=2.0)`. Cứ `progress_interval_s` giây (0 = mỗi vòng, đo bằng `time.monotonic`) gọi `on_progress(snapshot)` rồi `should_stop()`; True thì thoát vòng. `snapshot` có `iteration`, `n_iterations`, `best_reward` (None nếu bảng rỗng), `evaluations`, `failed_evaluations`, `gated_evaluations`, `elapsed_s`. Hàm trả lý do dừng: `budget`, `patience`, `entropy` hoặc `stopped`; nếu có `on_progress` thì gọi thêm một lần cuối với snapshot kèm `stop_reason`. Callback không đụng `self.rng` nên cùng seed vẫn cho cùng bảng xếp hạng (có test).
- Mỗi ứng viên trong bảng xếp hạng mang `template`, `window`, `z_score`, `threshold_upper`, `threshold_lower` để chạy lại đúng.

**Seed**: `MCTSEngine(seed=...)` tạo một `random.Random(seed)` riêng; mọi ngẫu nhiên của tìm kiếm (chọn nước chưa thử, rollout, hoà điểm UCT) đi qua nó. Cùng seed + cùng dữ liệu + cùng blueprint ⇒ cùng bảng xếp hạng (có test). Đưa ra ngoài bằng `main.py mcts --seed N` (`run_mcts_pipeline(seed=)`, `process_timeframe(seed=)`); không đặt ⇒ không tái lập được. Mọi khung dùng cùng seed nhưng mỗi khung có engine riêng.

**Mã xuất ra** (`RunMCTS.generate_strategy_code`): tệp `CustomStrategy(AlphaStrategy)` import đúng các `ts_*` nó dùng từ `core_engine.AlphaPrimitives`, tự dựng vị thế như `compute_positions`, chạy được qua `AlphaBacktestEngine.run`. Test dựng lại điểm Calmar, số lệnh và chuỗi vị thế của ứng viên tốt nhất từ tệp này.

⛔ Còn hở:
- Chỗ BOOLEAN ở độ sâu tối đa vượt giới hạn tối đa một tầng (so sánh `greater_than` / `less_than` / `equal` với hai lá), vì không có lá BOOLEAN.
- Đã đo 17 / 141 lượt chấm lỗi (khung 60m, seed 1, 300 vòng, blueprint `sub(ts_mean(?), ts_mean(?))`) vì `ts_*` nhận biểu thức toàn hằng số, ví dụ `ts_mean((0.2 + 0.5), 10)`; chúng nay được đếm và ghi log thay vì bị nuốt.
- Gốc RATIO vẫn dùng ngưỡng 60–80 / 20–40 (chưa sửa; ngoài phạm vi nối lại pipeline).

### 3.3 Kiểm định 3 tầng (`HMMValidation.py`)

- `precompute_hmm_synthetic_data(data_by_timeframe, force_retrain, n_paths)` nhận DataFrame lịch sử, không tự nạp. Mỗi mục cache là một tệp `data/MCdata/synthetic/{tf}_{khoá}.pkl`; khoá là băm của tên khung + dấu vân tay dữ liệu (số dòng, mốc đầu/cuối, SHA-256 của chỉ số và OHLCV) + tham số sinh (số đường, số trạng thái, hệ số căng thẳng, cỡ khối). Tệp lưu kèm siêu dữ liệu và được so khớp khi nạp, nên đường sinh từ dữ liệu khác không bao giờ được dùng lại. Tệp cũ `synthetic_data.pkl` không có siêu dữ liệu: không nạp, không xoá; khi còn tệp đó mà thiếu mục khớp thì khung bị bỏ qua kèm thông báo, chạy `--retrain-hmm` để dựng (bộ lọc HMM của khung đó bị bỏ qua cho tới lúc đó).
- HMM Gauss 3 trạng thái trên (log-lợi suất, độ lệch chuẩn 20 bar, tỷ lệ khối lượng). Đường giả lập: chạy chuỗi Markov, mỗi trạng thái chép một khối 20 bar lịch sử bắt đầu ở trạng thái đó. Biến thể "căng thẳng": xác suất chuyển vào trạng thái biến động cao × 1.5. 500 đường mỗi khung. Chỉ số thời gian của đường giả lập lấy từ lịch giao dịch của chính dữ liệu nguồn (cùng số bar mỗi ngày), để gom theo ngày ra đúng số phiên.
- Tầng 1 sống sót: < 5 % số đường có sụt giảm ≤ −23 %.
- Tầng 2: Kelly > 0 và lãi trung bình mỗi lệnh ≥ 3 × phí trung bình.
- Tầng 3: CAGR trung bình > 6 %/năm và Sharpe trung bình > mua-và-giữ trên cùng các đường chuẩn (`calculate_buy_hold_metrics`, tính tại chỗ bằng cùng hàm quy đổi; không còn đọc `results/benchmark_hmm_baseline.json`, tệp đó là số đo cũ và không gắn với dữ liệu nào).

Đã đo: bộ giả lập giữ độ dài chế độ 0.72–0.92 lần thực tế, sụt giảm mua-và-giữ tương đương hoặc nhẹ hơn thực tế.
Quy đổi theo năm: `calculate_metrics_for_result` gọi `compute_metrics` (Sharpe theo lợi suất ngày × √252; CAGR theo thời gian lịch trôi qua `(mốc cuối − mốc đầu)/365.25 ngày`) cho Sharpe và CAGR; sụt giảm vẫn tính theo bar. CAGR mua-và-giữ 2020–2024 đo lại ≈ 8.9 % ở cả 1m, 30m, 60m. Tệp 1m/5m/15m/30m thiếu 126 phiên (1 121 ngày so với 1 247 ở 1H, rải rác 2023-03-22 → 2024-03-14); CAGR đếm số phiên / 252 từng làm lệch 10.1 % so với 9.0 %, nay đã đổi sang thời gian lịch.

## 4. Backtest (`core_engine/BacktestEngine.py`)

- Tín hiệu bar t khớp ở bar t+1 (`shift(1)`); đã kiểm: không nhìn trước tương lai.
- Đầu vào `strategy.run_algorithm(df)` phải trả **`pd.Series`** vị thế mục tiêu trong [−1, 1].
- Số hợp đồng cố định theo vốn ban đầu (1 tỷ VND) và giá bar đầu: `N = round(|w|·E0 / (P0 · 100 000 · 0.285))`.
- Phí 6 000 VND / hợp đồng / chiều, tính trên phần chênh số hợp đồng.
- Gọi ký quỹ: xét giá xấu nhất trong bar (Low khi Long, High khi Short) so với ký quỹ duy trì 20 %; chạm ⇒ đóng hết, đóng băng vốn.
- Đáo hạn: bar cuối của ngày Thứ Năm thứ ba trong tháng (theo ngày có trong dữ liệu) bị phạt 2 điểm + 2 lần phí mỗi hợp đồng đang giữ.
- Không có trượt giá.
- `load_data(tf)` đọc CSV và lọc `BACKTEST_START → BACKTEST_END` (2020-01-01 → 2025-01-01); `'60m'` đọc tệp `1H`. Dữ liệu 2018–2019 và 2025 hiện không dùng.

## 5. Chỉ số

- `CalculateMetrics.compute_metrics`: Sharpe / Sortino / biến động trên lợi suất ngày × √252; CAGR (và Calmar, vào điểm thưởng MCTS) theo thời gian lịch `(mốc cuối − mốc đầu)/365.25 ngày`, tối thiểu 1 ngày, nên phiên thiếu trong dữ liệu không làm lệch.
- `HMMValidation.calculate_metrics_for_result`: dùng lại `compute_metrics` (mục 3.3).

## 6. Toán tử `AlphaPrimitives`

`ts_mean, ts_sum, ts_max, ts_min, ts_rank, ts_zscore, ts_argmax, ts_argmin, ts_corr`, viết bằng `sliding_window_view`. Đã kiểm: kết quả trên chuỗi đầy đủ và chuỗi cắt bớt trùng nhau tuyệt đối (không nhìn trước). `benchmark_primitives.py` so khớp pandas trong sai số 1e-5; `ts_argmax` / `ts_argmin` nhanh hơn pandas khoảng 13–15 lần.
Chưa có toán tử trễ / sai phân (`ts_delay`, `ts_delta`).

## 7. Nguồn gốc ý tưởng thiết kế

| Ý | Nguồn |
|---|---|
| Kiểm thứ nguyên trước khi ghép nhánh | Alpha² (`docs/references/2406.16505v1.pdf`) |
| MCTS lan truyền giá trị lớn nhất (tìm trường hợp tốt nhất) | RiskMiner (`docs/references/3677052.3698613.pdf`) |
| LLM chạy tách khỏi MCTS, chỉ sinh cấu trúc | Lựa chọn thiết kế của dự án (bài Chain-of-Alpha từng được dẫn đã bị rút khỏi arXiv) |
| Phạt tương quan với danh mục, giữ z-score tĩnh để dễ diễn giải | Lựa chọn thiết kế của dự án |
