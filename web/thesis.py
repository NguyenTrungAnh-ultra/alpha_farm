"""
All prose of the thesis web pages: chapter list and statuses, intros, captions, plain-words
descriptions and the sentences that read a result. Templates only render what is defined here.

Sentences that quote numbers are built by functions from the computed result, never typed in.
Item fields: key, role (chính / phụ / chẩn đoán; absent when the item shows no metric), label (numbered caption prefix), title, chapter (path), rq, needs (availability
key that makes the item "done"; None = no result yet).
"""

import math
from typing import Dict, List, Optional

from strategy_workflows.BlueprintGeneration import MAX_GENERATED_TOKENS, MAX_REPLY_ATTEMPTS
from strategy_workflows.PlantedSignal import NEAR_CORRELATION
from strategy_workflows.RunRQ1 import DETECTION_BUDGET, DETECTION_CONFIG, IC_LEVELS, PRIMARY_BUDGETS, PRIMARY_IC
from strategy_workflows.SearchConfigs import BudgetPlan
from strategy_workflows.Statistics import FISHER_ALPHA
from utilities.AppConfig import MCTS_MAX_DEPTH

def num(n) -> str:
    """Integer with '.' as the thousands separator (Vietnamese convention)."""
    return f"{int(n):,}".replace(',', '.')


CONFIG_LABELS = {'llm_mcts': 'LLM + MCTS', 'mcts_only': 'MCTS không LLM', 'random': 'Tìm ngẫu nhiên',
                 'llm_only': 'LLM không tìm', 'buy_hold': 'Mua và giữ', 'tsmom': 'TSMOM'}


def config_label(key: str) -> str:
    return CONFIG_LABELS.get(key, key)


STATUS_LABELS = {'done': 'Xong', 'progress': 'Đang làm', 'none': 'Chưa có kết quả'}
STATUS_MARKS = {'done': '✅', 'progress': '🔧', 'none': '–'}

PLACEBO_TITLE = 'Kết quả: placebo (RQ2, kiểm soát âm)'
PLANTED_TITLE = 'Kết quả: bài cài tín hiệu (RQ2, kiểm soát dương)'
RQ1_TITLE = 'Kết quả: vai trò của LLM (RQ1)'

CHAPTERS: List[Dict] = [
    {'number': 1, 'title': 'Tổng quan', 'path': '/', 'status': 'done'},
    {'number': 2, 'title': 'Dữ liệu', 'path': '/data', 'status': 'done'},
    {'number': 3, 'title': 'Phương pháp', 'path': '/method', 'status': 'progress'},
    {'number': 4.1, 'title': PLANTED_TITLE, 'path': '/results/planted', 'needs': 'planted_detection'},
    {'number': 4.2, 'title': PLACEBO_TITLE, 'path': '/results/placebo', 'needs': 'placebo_runs'},
    {'number': 4.3, 'title': RQ1_TITLE, 'path': '/results/rq1', 'needs': 'rq1_primary'},
    {'number': 4.4, 'title': 'Kết quả: chuỗi ngoài mẫu (walk-forward)', 'path': '/results/walkforward',
     'status': 'none'},
]

ITEMS: List[Dict] = [
    {'key': 'data_bars', 'label': 'Bảng 2.1', 'title': 'Dữ liệu VN30F1M 60 phút và số nến từng đoạn walk-forward',
     'chapter': '/data', 'rq': None, 'needs': 'data'},
    {'key': 'flow', 'label': 'Hình 3.1', 'title': 'Sơ đồ luồng chính', 'chapter': '/method', 'rq': None,
     'status': 'done'},
    {'key': 'windows', 'label': 'Hình 3.2', 'title': 'Cửa sổ walk-forward', 'chapter': '/method', 'rq': None,
     'status': 'done'},
    {'key': 'blueprints', 'label': 'Bảng 3.1', 'title': 'Bộ blueprint đã đóng băng cho RQ1', 'chapter': '/method',
     'rq': None, 'needs': 'blueprint_set'},
    {'key': 'configs', 'label': 'Bảng 3.2', 'title': 'Các cấu hình so sánh', 'chapter': '/method', 'rq': None,
     'status': 'done'},
    {'key': 'feedback', 'label': 'Bảng 3.3', 'title': 'Vòng phản hồi và các mốc ngân sách', 'chapter': '/method',
     'rq': None, 'status': 'done'},
    {'key': 'space', 'label': 'Bảng 3.4', 'title': 'Kích thước không gian tìm kiếm', 'chapter': '/method',
     'rq': None, 'needs': 'blueprint_set'},
    {'key': 'planted_signals', 'label': 'Bảng 4.1', 'title': 'Bốn tín hiệu cài sẵn A', 'chapter': '/results/planted',
     'rq': 'RQ2', 'needs': 'planted_formulas'},
    {'key': 'planted_threshold', 'role': 'chính', 'label': 'Bảng 4.2', 'title': 'Ngưỡng phát hiện theo A',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_detection'},
    {'key': 'planted_table', 'role': 'phụ', 'label': 'Bảng 4.3', 'title': 'Tỷ lệ tìm lại gần theo A và IC mục tiêu',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_summary'},
    {'key': 'planted_near', 'role': 'phụ', 'label': 'Hình 4.1', 'title': 'Tỷ lệ tìm lại gần theo IC mục tiêu, từng A',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_summary'},
    {'key': 'placebo_dist', 'role': 'chính', 'label': 'Hình 4.2', 'title': 'Sharpe ngoài mẫu của các bộ placebo so với lần chạy thật',
     'chapter': '/results/placebo', 'rq': 'RQ2', 'needs': 'placebo_runs'},
    {'key': 'rq1_primary', 'role': 'chính', 'label': 'Bảng 4.4',
     'title': 'LLM + MCTS so với MCTS không LLM: bốn phép Fisher hai phía chỉnh Holm', 'chapter': '/results/rq1',
     'rq': 'RQ1', 'needs': 'rq1_primary'},
    {'key': 'rq1_budget', 'role': 'phụ', 'label': 'Hình 4.3', 'title': 'Tỷ lệ tìm lại gần theo ngân sách, từng A',
     'chapter': '/results/rq1', 'rq': 'RQ1', 'needs': 'rq1_summary'},
    {'key': 'rq1_coverage', 'role': 'chẩn đoán', 'label': 'Bảng 4.5',
     'title': 'A nằm trong hay ngoài vùng của bộ blueprint ban đầu', 'chapter': '/results/rq1', 'rq': 'RQ1',
     'needs': 'coverage'},
    {'key': 'rq1_touch', 'role': 'phụ', 'label': 'Bảng 4.6', 'title': 'Lần đầu chạm A: số vòng và thời gian',
     'chapter': '/results/rq1', 'rq': 'RQ1', 'needs': 'rq1_touch'},
    {'key': 'rq1_walkforward', 'role': 'phụ', 'label': 'Bảng 4.7',
     'title': 'Sharpe ngoài mẫu walk-forward của các cấu hình (mô tả)', 'chapter': '/results/rq1', 'rq': 'RQ1',
     'needs': 'wf_comparison'},
    {'key': 'wf_table', 'role': 'phụ', 'label': 'Bảng 4.8', 'title': 'Sharpe ngoài mẫu theo cửa sổ walk-forward',
     'chapter': '/results/walkforward', 'rq': 'RQ1, RQ2', 'needs': None},
    {'key': 'wf_curve', 'role': 'chính', 'label': 'Hình 4.4', 'title': 'Chuỗi lợi suất ngoài mẫu nối 7 cửa sổ',
     'chapter': '/results/walkforward', 'rq': 'RQ1, RQ2', 'needs': None},
]

ITEM_BY_KEY = {item['key']: item for item in ITEMS}

OVERVIEW_INTRO = ('Trang này theo thứ tự các chương của luận văn. Mỗi bảng và hình có số thứ tự, nói nó trả lời '
                  'câu hỏi nghiên cứu nào, và kèm một câu đọc kết quả. Chỉ hiện cấu hình đã chốt cho luận văn.')

DATA_INTRO = ('Dữ liệu là nến 60 phút của hợp đồng tương lai chỉ số VN30F1M (nguồn DNSE). Mọi cửa sổ walk-forward '
              'và bài cài tín hiệu đều cắt từ cùng một tệp này. Bảng dưới đếm nến từng đoạn của mỗi cửa sổ '
              'trực tiếp từ tệp dữ liệu.')

METHOD_INTRO = ('Sơ đồ dưới là quy trình được đánh giá. Đối tượng đánh giá là cả quy trình, không phải một alpha riêng lẻ. '
                'Di chuột vào một ô (hoặc chạm trên điện thoại) để xem chi tiết.')

WINDOWS_CAPTION = ('Cửa sổ walk-forward nở dần: đoạn học bắt đầu cố định, đoạn kiểm định là 12 tháng trước đoạn đánh giá, '
                   'đoạn đánh giá dài 6 tháng và dịch 6 tháng mỗi cửa sổ.')

BLUEPRINT_CAPTION = ('Bộ blueprint ban đầu do LLM sinh một lần và được đóng băng cho mọi cấu hình có LLM (LLM + MCTS còn viết thêm '
                     'blueprint ở vòng phản hồi). Mỗi blueprint là một khung '
                     'công thức có ô `?`; "số cách điền" là số công thức hợp thứ nguyên MCTS có thể dựng từ nó '
                     f'(độ sâu tối đa {MCTS_MAX_DEPTH}).')
CONFIGS_CAPTION = ('Các cấu hình tiêu cùng một ngân sách đánh giá và kết thúc bằng cùng phép chọn top-5 trên đoạn kiểm định, '
                   'nên khác biệt chỉ nằm ở cách sinh ứng viên.')
FEEDBACK_CAPTION = 'Một lượt của LLM + MCTS (một cửa sổ walk-forward hoặc một lượt bài cài tín hiệu).'
SPACE_CAPTION = ('Blueprint thu vùng tìm kiếm: "sớm hơn" chỉ đúng khi tín hiệu nằm trong vùng đó. Số tính bằng cách đếm chính xác '
                 'theo luật của MCTS, không đếm tham số khuôn.')

CONFIG_ROWS: List[Dict[str, str]] = [
    {'name': 'LLM + MCTS có phản hồi', 'key': 'llm_mcts',
     'how': 'LLM viết bộ blueprint ban đầu (đóng băng); MCTS điền các ô `?`; sau giai đoạn A, LLM xem các biểu thức tốt '
            'nhất trên đoạn học và viết blueprint mới cho giai đoạn B.'},
    {'name': 'MCTS không LLM', 'key': 'mcts_only',
     'how': 'MCTS bắt đầu từ một ô `?` trần dưới mỗi khuôn NORMALIZED, BOOLEAN, RATIO; ngân sách chia đều ba phần.'},
    {'name': 'Tìm ngẫu nhiên', 'key': 'random',
     'how': 'Công thức hợp thứ nguyên sinh ngẫu nhiên theo kích thước (ramped half-and-half), cùng số mẫu với ngân sách.'},
    {'name': 'LLM không tìm', 'key': 'llm_only',
     'how': 'LLM viết một lần một bộ công thức hoàn chỉnh rồi đóng băng; mỗi cửa sổ chỉ chấm chúng trên lưới tham số khuôn. '
            'Chỉ chạy walk-forward thật, một seed.'},
    {'name': 'Mua và giữ, TSMOM', 'key': 'buy_hold, tsmom',
     'how': 'Hai tham chiếu không tìm: luôn long; dấu lợi suất quá khứ với độ dài chọn theo Sharpe kiểm định. '
            'Chỉ chạy walk-forward thật, một seed.'},
]

PLANTED_QUESTION = ('Câu hỏi: nếu trong dữ liệu có một tín hiệu biết trước, quy trình có tìm lại được nó không? '
                    'Đây là kiểm soát dương của RQ2 (ngưỡng phát hiện) và cũng là nơi đo phép so chính của RQ1 (trang RQ1).')
PLANTED_METHOD = [
    'Xáo thứ tự lợi suất từng nến trong mỗi đoạn dữ liệu thật để xoá mọi cấu trúc có sẵn, giữ khối lượng và hình dạng '
    'trong nến.',
    'Cài vào lợi suất kế tiếp một phần tỷ lệ với tín hiệu A, hiệu chỉnh sao cho IC (tương quan hạng của A với lợi suất '
    'nến sau) đạt một mức mục tiêu biết trước: 0 (không cài gì), ' + ' hoặc '.join(f'{x:g}' for x in IC_LEVELS) + '.',
    'Chạy đúng quy trình luận văn (LLM sinh blueprint, MCTS có vòng phản hồi, chọn top-5 trên đoạn kiểm định) trên dữ liệu '
    'đã cài, rồi xem top-5 có chứa một công thức giống A hay không.',
]
PLANTED_SIGNALS_RQ = ('Mô tả cho RQ2: bốn tín hiệu mà quy trình được yêu cầu tìm lại. Hai tín hiệu kinh điển là công thức '
                      'quen thuộc; hai tín hiệu lạ do máy sinh ngẫu nhiên với số toán tử cho trước, sau khi loại những công thức '
                      'không dừng, quá đông hoặc trùng dạng với hai tín hiệu kinh điển.')
PLANTED_THRESHOLD_RQ = ('Trả lời RQ2: với từng A, mức IC thấp nhất mà quy trình LLM + MCTS tìm lại gần A nhiều hơn khi không '
                        'cài gì (kiểm định Fisher một phía so với IC 0).')
PLANTED_TABLE_RQ = ('Bổ sung cho RQ2: số seed tìm lại gần trên số seed của LLM + MCTS, theo A và IC mục tiêu, kèm khoảng tin '
                    'cậy Wilson 95% và p Fisher một phía so với IC 0. Không dùng một mình để kết luận.')
PLANTED_NEAR_RQ = ('Bổ sung cho RQ2: cùng số liệu với Bảng 4.3, mỗi ô là một A. Đường nét đứt là khoảng tin cậy Wilson 95%.')
PLANTED_PENDING = ('chưa có. Cần chạy `main.py rq1 search` rồi `main.py rq1 summary` để có kết quả bài cài tín hiệu của '
                   'RQ1.')
PLANTED_FORMULAS_PENDING = 'chưa có. Cần `main.py rq1 formulas` (tệp planted_formulas.json).'
MISSING = 'chưa có'
ILLUSTRATION_TITLE = 'Minh hoạ: cài tín hiệu làm gì với giá'
ILLUSTRATION_LINK = 'Xem minh hoạ một bộ dữ liệu: giá thật, giá placebo, giá đã cài và tín hiệu'
PLANTED_ILLUSTRATION_MISSING = 'Chưa có kết quả bài cài tín hiệu (thiếu runs.csv trong thư mục kết quả luận văn).'

PLACEBO_QUESTION = ('Câu hỏi: hệ thống có tốt hơn chính nó chạy trên dữ liệu placebo, nơi không có gì để tìm không? '
                    'Đây là kiểm soát âm của RQ2.')
PLACEBO_METHOD = ('Mỗi bộ placebo xáo thứ tự lợi suất của dữ liệu rồi chạy đúng hệ thống luận văn (LLM + MCTS có vòng phản '
                  'hồi) theo quy trình walk-forward (7 cửa sổ, một seed MCTS). Sharpe của bộ là Sharpe năm của chuỗi lợi '
                  'suất ngày ngoài mẫu nối từ các cửa sổ.')
PLACEBO_DIST_RQ = ('Trả lời RQ2: hệ thống tự tạo ra Sharpe ngoài mẫu cỡ nào khi không có tín hiệu. Mỗi chấm là một bộ '
                   'placebo; vạch ngang là Sharpe placebo lớn nhất.')
PLACEBO_MISSING = ('Chưa có kết quả placebo (thiếu summary.csv trong thư mục walk-forward của hệ thống LLM + MCTS có '
                   'vòng phản hồi; cần `main.py walkforward placebo` rồi `summary`).')
PLACEBO_P_PENDING = 'chưa có, chờ lần chạy thật'

RQ1_QUESTION = ('Câu hỏi: cùng giới hạn độ dài công thức, LLM đưa MCTS tới tín hiệu đúng sớm hơn hay chặn đường tới nó? '
                'Đo trên bài cài tín hiệu, nơi đáp án biết trước.')
def seed_phrase(seeds: Optional[int]) -> str:
    """'10 seed', or a vague count when the result files do not say."""
    return f"{seeds} seed" if seeds else 'ít seed'


def rq1_design(seeds: Optional[int]) -> List[str]:
    """The three design sentences of the RQ1 page; `seeds` is the seed count per cell read from summary.csv."""
    return [
        f"Bốn tín hiệu A (Bảng 4.1) được cài vào dữ liệu xáo ở từng mức IC mục tiêu; mỗi cấu hình chạy {seed_phrase(seeds)} cho mỗi A; "
        'IC 0 không cài gì nên một lượt được chấm với cả bốn A.',
        f'Mỗi lượt ghi lại top-5 tại các mốc ngân sách; mốc {num(BudgetPlan().phase_a)} là hết giai đoạn A, trước phản hồi của '
        'LLM. Tìm lại gần nghĩa là top-5 có công thức với |Spearman| ≥ ' + f'{NEAR_CORRELATION:g}' + ' với A.',
        f"Phép so chính duy nhất: LLM + MCTS với MCTS không LLM ở IC {PRIMARY_IC:g}, gộp theo loại A (kinh điển, lạ), tại "
        f"{' và '.join(f'{num(b)}' for b in PRIMARY_BUDGETS)}: bốn kiểm định Fisher hai phía (LLM có thể chặn đường), chỉnh Holm. "
        'Mọi ô khác chỉ mô tả, không đọc p.',
    ]


RQ1_PRIMARY_RQ = ('Trả lời RQ1: LLM + MCTS có tìm lại gần A khác MCTS không LLM không (hai phía), tại hai mốc ngân sách, chia '
                  'theo loại A. Phép so chính duy nhất; p đã chỉnh Holm cho cả bốn phép.')
RQ1_BUDGET_RQ = ('Bổ sung cho RQ1: tỷ lệ tìm lại gần theo ngân sách ở IC {ic:g}, mỗi ô là một A, mỗi đường là một cấu hình, '
                 'dải là khoảng tin cậy Wilson 95%. Đường dọc đánh dấu mốc {mark}: hết giai đoạn A, trước phản hồi.')
RQ1_COVERAGE_RQ = ('Chẩn đoán cho RQ1: giải thích vì sao LLM + MCTS có thể không tới A ở mốc trước phản hồi. A ngoài vùng '
                   'của bộ blueprint ban đầu thì chỉ vòng phản hồi mới mở được đường tới nó.')
RQ1_TOUCH_RQ = ('Bổ sung cho RQ1: số vòng MCTS và thời gian thật (tính cả LLM) tới lần đầu bảng xếp hạng có công thức với '
                '|Spearman| ≥ ' + f'{NEAR_CORRELATION:g}' + ' với A, trung vị chỉ qua các lượt đã chạm; cột "đã chạm" cho '
                'biết bao nhiêu lượt đã chạm.')
RQ1_WALKFORWARD_RQ = ('Bổ sung cho RQ1 (mô tả): Sharpe năm ngoài mẫu của từng cấu hình trong lần chạy thật walk-forward, '
                      'và chênh lệch với LLM + MCTS trên các ngày chung, có khoảng tin cậy bootstrap khối dừng cặp đôi. '
                      'Không có p; chỉ phân biệt được chênh lớn.')
RQ1_PENDING = 'chưa có. Cần `main.py rq1 search` rồi `main.py rq1 summary`.'
RQ1_COVERAGE_PENDING = 'chưa có. Cần `main.py rq1 coverage`.'
RQ1_WALKFORWARD_PENDING = 'chưa có. Cần `main.py walkforward real` rồi `main.py walkforward summary` (cho comparison.csv).'
RQ1_PRIMARY_PENDING = 'chưa có. Cần `main.py rq1 search` rồi `main.py rq1 summary` (cho primary_tests.csv).'

PENDING_CHAPTERS: Dict[str, Dict] = {
    'walkforward': {
        'title': 'Kết quả: chuỗi ngoài mẫu (walk-forward)',
        'rq': 'RQ1, RQ2',
        'answers': 'Chỉ số chính của luận văn: Sharpe năm của chuỗi lợi suất ngày ngoài mẫu 2022-07 → 2025-12, '
                   'dùng cho cả so sánh RQ1 và so với placebo ở RQ2.',
        'will_show': ['Bảng 4.8: Sharpe ngoài mẫu theo cửa sổ và seed.',
                      'Hình 4.4: chuỗi lợi suất ngoài mẫu nối 7 cửa sổ.'],
        'primary': 'wf_sharpe', 'metrics': ['wf_sharpe', 'window_sharpe', 'max_drawdown'],
        'condition': 'Cần đóng băng cấu hình (bộ blueprint, reward, bảng cửa sổ, ngân sách, seed) rồi chạy dữ liệu thật '
                     'đúng một lần; chưa làm.',
    },
}

PLACEBO_PRIMARY = 'placebo_p'
PLACEBO_METRICS = ['placebo_p', 'placebo_dist']
PLANTED_PRIMARY = 'detection_threshold'
PLANTED_METRICS = ['detection_threshold', 'target_ic', 'near', 'fisher_p', 'crowding', 'adf_p']
RQ1_PRIMARY = 'holm_p'
RQ1_METRICS = ['holm_p', 'near', 'in_region', 'completions', 'first_touch', 'wf_sharpe', 'wf_diff', 'rho']
RQ1_ROLE_OVERRIDES = {'wf_sharpe': 'phụ'}
PRIMARY_BOX_TITLE = 'Chỉ số chính'
METRIC_LIST_TITLE = 'Chỉ số dùng trong chương này'
ROLE_HELP = {'chính': 'trả lời trực tiếp câu hỏi của chương',
             'phụ': 'bổ sung, không dùng để kết luận một mình',
             'chẩn đoán': 'giải thích vì sao, không phải kết quả'}

# One glossary for every page. Keys must not clash with dict method names (items, keys, values).
METRICS: Dict[str, Dict[str, str]] = {
    'target_ic': {'name': 'IC mục tiêu',
                  'measures': 'Mức tương quan hạng giữa tín hiệu A và lợi suất nến sau mà ta chủ động cài vào dữ liệu.',
                  'reading': 'Càng cao thì tín hiệu càng dễ thấy; 0 nghĩa là không cài gì (placebo).',
                  'role': 'phụ'},
    'detection_threshold': {
        'name': 'Ngưỡng phát hiện',
        'measures': f'Mức IC > 0 thấp nhất mà tỷ lệ tìm lại gần của {config_label(DETECTION_CONFIG)} ở ngân sách {num(DETECTION_BUDGET)} '
                    f'cao hơn ở IC 0 với p < {FISHER_ALPHA:g} (kiểm định chính xác Fisher một phía), tính riêng từng A.',
        'reading': 'Thấp hơn là nhạy hơn. "Chưa xác định" nghĩa là không mức IC nào đạt; mỗi mức chỉ có {seeds} nên '
                   'kiểm định có ít sức, và điều đó không có nghĩa là quy trình không phát hiện được.',
        'role': 'chính'},
    'fisher_p': {'name': 'p Fisher so với IC 0',
                 'measures': 'Xác suất thấy ít nhất chừng ấy lần tìm lại gần nếu mức IC đó không khác gì IC 0 '
                             '(kiểm định chính xác Fisher một phía, so tỷ lệ tìm lại gần với IC 0).',
                 'reading': f'Nhỏ hơn {FISHER_ALPHA:g} thì coi là khác IC 0; ngưỡng phát hiện là mức IC thấp nhất đạt điều đó.',
                 'role': 'phụ'},
    'near': {'name': 'Tìm lại gần',
             'measures': 'Số seed mà top-5 được chọn có ít nhất một công thức với alpha tương quan hạng tuyệt đối '
                         f'với A từ {NEAR_CORRELATION:g} trở lên, tại một mốc ngân sách.',
             'reading': 'Là tỷ lệ k/n theo IC và A. Tỷ lệ ở IC 0 là mức "tìm lại" do ngẫu nhiên.',
             'role': 'phụ'},
    'crowding': {'name': 'Độ đông của A',
                 'measures': 'Tỷ lệ công thức ngẫu nhiên hợp lệ (mẫu 10.000 công thức) có tương quan hạng tuyệt đối với A '
                             f'từ {NEAR_CORRELATION:g} trở lên trên đoạn tìm.',
                 'reading': 'Nhỏ nghĩa là tìm lại gần khó xảy ra do tình cờ. Luật chọn A loại những A có tỷ lệ này từ 1% '
                            'trở lên.',
                 'role': 'chẩn đoán'},
    'adf_p': {'name': 'p của kiểm định ADF',
              'measures': 'p-value kiểm định nghiệm đơn vị (Augmented Dickey-Fuller) của giá trị A trên đoạn tìm.',
              'reading': 'Nhỏ hơn 0.05 là chuỗi dừng. Luật chọn A loại những A không dừng, vì tương quan hạng của chuỗi '
                         'không dừng dễ cho kết quả giả.',
              'role': 'chẩn đoán'},
    'holm_p': {'name': 'p Fisher hai phía, chỉnh Holm',
               'measures': f'So tỷ lệ tìm lại gần của LLM + MCTS với MCTS không LLM ở IC {PRIMARY_IC:g}, gộp theo loại A '
                           '(kinh điển, lạ) và theo ngân sách (' + ', '.join(f'{num(b)}' for b in PRIMARY_BUDGETS) + '): bốn '
                           'kiểm định chính xác Fisher hai phía, chỉnh Holm cho cả họ bốn phép.',
               'reading': f'Nhỏ hơn {FISHER_ALPHA:g} thì hai cấu hình khác nhau (hai phía, vì LLM có thể chặn đường). '
                          'Cỡ mẫu nhỏ nên chỉ phân biệt được chênh lớn.',
               'role': 'chính'},
    'in_region': {'name': 'A trong vùng blueprint ban đầu',
                  'measures': f'Có ít nhất một blueprint của bộ đóng băng điền ra được đúng A (độ sâu tối đa {MCTS_MAX_DEPTH}).',
                  'reading': 'Ngoài vùng thì trước vòng phản hồi LLM + MCTS không thể tới A; chỉ phản hồi mới mở đường.',
                  'role': 'chẩn đoán'},
    'completions': {'name': 'Số cách điền của blueprint nhỏ nhất chứa A',
                    'measures': 'Số công thức hợp thứ nguyên mà blueprint nhỏ nhất trong các blueprint điền ra được A có '
                                'thể dựng.',
                    'reading': 'Càng nhỏ thì A càng dễ tìm trong vùng của nó; càng lớn thì tìm trong vùng vẫn khó.',
                    'role': 'chẩn đoán'},
    'first_touch': {'name': 'Lần đầu chạm A',
                    'measures': 'Số vòng MCTS và thời gian thật (tính cả thời gian LLM) tới lần đầu bảng xếp hạng có công '
                                f'thức với tương quan hạng tuyệt đối với A từ {NEAR_CORRELATION:g} trở lên.',
                    'reading': 'Trung vị chỉ qua các lượt đã chạm; đọc kèm số lượt chạm trên số lượt. Độ phân giải bằng một '
                               'đoạn MCTS.',
                    'role': 'phụ'},
    'placebo_p': {'name': 'p-value placebo',
                  'measures': 'Tỷ lệ bộ placebo (dữ liệu xáo, không có gì để tìm) có Sharpe ngoài mẫu không thấp hơn '
                              'lần chạy thật.',
                  'reading': 'Càng nhỏ càng khó là may mắn; với K bộ placebo, giá trị nhỏ nhất có thể là 1/(K+1), '
                             'tức 0.05 với 19 bộ, và chỉ đạt khi Sharpe thật vượt mọi bộ placebo.',
                  'role': 'chính'},
    'placebo_dist': {'name': 'Phân bố Sharpe placebo',
                     'measures': 'Sharpe ngoài mẫu của từng bộ placebo.',
                     'reading': 'Cho thấy hệ thống tự tạo ra Sharpe cỡ nào khi không có tín hiệu; lần chạy thật phải '
                                'nằm ngoài vùng này.',
                     'role': 'phụ'},
    'wf_sharpe': {'name': 'Sharpe năm ngoài mẫu',
                  'measures': 'Sharpe hằng năm hoá của chuỗi lợi suất ngày ngoài mẫu 2022-07 → 2025-12 nối từ 7 cửa sổ.',
                  'reading': 'Chỉ số chính của luận văn; lớn hơn là tốt hơn, so giữa cấu hình hoặc với placebo.',
                  'role': 'chính'},
    'wf_diff': {'name': 'Chênh Sharpe so với LLM + MCTS',
                'measures': 'Sharpe năm của LLM + MCTS trừ Sharpe năm của cấu hình, trên các ngày chung, kèm khoảng tin '
                            'cậy 95% theo bootstrap khối dừng cặp đôi.',
                'reading': 'Dương: LLM + MCTS cao hơn. Khoảng chứa 0 thì dữ liệu không phân biệt được hai cấu hình.',
                'role': 'phụ'},
    'rho': {'name': 'Tương quan lợi suất ngày',
            'measures': 'Tương quan Pearson giữa lợi suất ngày của cấu hình và của LLM + MCTS.',
            'reading': 'Cao nghĩa là hai chuỗi di chuyển cùng nhau, nên chênh Sharpe giữa chúng có khoảng tin cậy hẹp hơn.',
            'role': 'phụ'},
    'window_sharpe': {'name': 'Sharpe từng cửa sổ',
                      'measures': 'Sharpe năm hoá riêng của 6 tháng đánh giá mỗi cửa sổ.',
                      'reading': 'Cho thấy kết quả đều hay chỉ nhờ một cửa sổ; mỗi giá trị rất nhiễu.',
                      'role': 'phụ'},
    'max_drawdown': {'name': 'Sụt giảm lớn nhất',
                     'measures': 'Mức giảm lớn nhất của vốn từ đỉnh xuống đáy trong chuỗi ngoài mẫu.',
                     'reading': 'Cho biết rủi ro chịu đựng để có Sharpe đó; nhỏ hơn là tốt hơn.',
                     'role': 'phụ'},
}


def metric_entry(key: str, seeds: Optional[int] = None) -> Dict[str, str]:
    """One glossary entry with the `{seeds}` placeholder of its reading filled in."""
    entry = dict(METRICS[key])
    entry['reading'] = entry['reading'].replace('{seeds}', seed_phrase(seeds))
    return entry


def metric_rows(keys: List[str], roles: Optional[Dict[str, str]] = None, seeds: Optional[int] = None) -> List[Dict]:
    """Glossary rows (name, what it measures, how to read, role) for a chapter's list of metrics; `roles` overrides a role."""
    return [dict(metric_entry(k, seeds), key=k, **({'role': roles[k]} if roles and k in roles else {})) for k in keys]


def chapter_status(chapter: Dict, availability: Dict[str, bool]) -> str:
    if 'needs' in chapter:
        return 'done' if availability.get(chapter['needs']) else 'none'
    return chapter['status']


def item_status(item: Dict, availability: Dict[str, bool]) -> str:
    if item.get('needs'):
        return 'done' if availability.get(item['needs']) else 'none'
    return item.get('status', 'none')


def progress_rows(availability: Dict[str, bool]) -> List[Dict]:
    """Chapters and their numbered tables / figures as one flat list, in chapter order."""
    rows = []
    for chapter in CHAPTERS:
        status = chapter_status(chapter, availability)
        rows.append({'kind': 'chapter', 'role': '', 'label': f"Chương {chapter['number']}", 'title': chapter['title'],
                     'path': chapter['path'], 'rq': '', 'status': status, 'status_label': STATUS_LABELS[status],
                     'mark': STATUS_MARKS[status]})
        for item in ITEMS:
            if item['chapter'] == chapter['path']:
                item_state = item_status(item, availability)
                rows.append({'kind': 'item', 'role': item.get('role', ''), 'label': item['label'], 'title': item['title'],
                             'path': chapter['path'], 'rq': item['rq'] or '', 'status': item_state,
                             'status_label': STATUS_LABELS[item_state], 'mark': STATUS_MARKS[item_state]})
    return rows


# --------------------------------------------------------------------------- method chapter

_SUPERSCRIPT = str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹')


def sci(n: int) -> str:
    """A positive integer as 'm × 10ⁿ' with two significant digits."""
    mantissa, exponent = f"{n:.1e}".split('e')
    return f"{mantissa} × 10{str(int(exponent)).translate(_SUPERSCRIPT)}"


def feedback_steps(plan: BudgetPlan, n_blueprints: Optional[int]) -> List[Dict[str, str]]:
    """The stages of one LLM + MCTS run with their budgets, taken from the budget plan."""
    phase_b = plan.total - plan.phase_a
    first = f"{n_blueprints} blueprint" if n_blueprints else 'Các blueprint'
    each = f", mỗi blueprint {num(plan.phase_a // n_blueprints)} vòng" if n_blueprints else ''
    return [
        {'stage': 'Giai đoạn A',
         'text': f"{first} đóng băng chia đều {num(plan.phase_a)} vòng MCTS{each}, trên đoạn học."},
        {'stage': 'Phản hồi',
         'text': f"Lấy {plan.feedback_expressions} biểu thức khác nhau tốt nhất theo reward đoạn học (bỏ cửa sổ khỏi biểu thức rồi "
                 'mới khử trùng); đưa LLM biểu thức đã bỏ cửa sổ, reward và IC đoạn học (không đoạn kiểm định hay đánh giá, '
                 f"không tên thị trường). LLM viết {plan.feedback_blueprints} blueprint mới trong một yêu cầu, cùng luật hợp lệ "
                 'với bộ ban đầu, và thêm một yêu cầu sửa cho các ý bị loại. Mỗi yêu cầu giới hạn '
                 f"{num(MAX_GENERATED_TOKENS)} token sinh ra (tính cả thinking); bị cắt hoặc rỗng thì hỏi lại tối đa "
                 f"{MAX_REPLY_ATTEMPTS - 1} lần với seed mới. Không nhận được blueprint mới nào thì giai đoạn B dùng lại bộ ban đầu."},
        {'stage': 'Giai đoạn B', 'text': f"{plan.feedback_blueprints} blueprint mới chia đều {num(phase_b)} vòng còn lại."},
        {'stage': 'Mốc ngân sách',
         'text': 'Bảng xếp hạng được chụp tại ' + ', '.join(f"{num(c)}" for c in plan.checkpoints)
                 + f" vòng, không chạy thêm. Mốc {num(plan.phase_a)} nằm trước phản hồi."},
        {'stage': 'Chọn top-5',
         'text': 'Các biểu thức tốt nhất của cả hai giai đoạn được chấm lại trên đoạn kiểm định, lấy top-5; cùng phép chọn '
                 'với mọi cấu hình.'},
    ]


def reading_blueprints(summary: Dict) -> str:
    """Operator coverage and size of the frozen set."""
    missing = ', '.join(f"`{op}`" for op in summary['operators_missing'])
    tail = f"; còn thiếu {missing}" if summary['operators_missing'] else ''
    smallest = min((b['completions'] for b in summary['blueprints'] if b['completions']), default=None)
    small = f" Blueprint nhỏ nhất có {num(smallest)} cách điền." if smallest else ''
    return (f"Đọc: {summary['count']} blueprint dùng {summary['operators_used']}/{summary['operators_total']} toán tử đã cài"
            f"{tail}. Tổng số cách điền của bộ là {sci(summary['set_size'])}.{small}")


def reading_space(summary: Dict) -> str:
    set_size, grammar = summary['set_size'], summary['grammar_size']
    return (f"Đọc: cả ngữ pháp có {sci(grammar)} công thức, bộ blueprint thu vùng tìm kiếm còn {sci(set_size)}, "
            f"nhỏ hơn {sci(round(grammar / set_size))} lần." if set_size else '')


# --------------------------------------------------------------------------- readings of results


def _fmt(value, digits: int = 2) -> str:
    return '–' if value is None or (isinstance(value, float) and not math.isfinite(value)) else f"{value:.{digits}f}"


def _ic(value: float) -> str:
    return f"{value:g}"


def _p(value) -> str:
    return '–' if value is None or not math.isfinite(value) else f"{value:.3f}"


def reading_signals(rows: List[Dict]) -> str:
    """How many of the A are classical or odd, and the largest crowding share and ADF p."""
    if not rows:
        return ''
    classical = [r['name'] for r in rows if r['kind'] == 'classical']
    odd = [r['name'] for r in rows if r['kind'] != 'classical']
    crowded = [r for r in rows if r['crowding_share'] is not None]
    adf = [r for r in rows if r['adf_p'] is not None]
    parts = [f"{len(classical)} tín hiệu kinh điển ({', '.join(classical)}) và {len(odd)} tín hiệu lạ ({', '.join(odd)})"]
    if crowded:
        top = max(crowded, key=lambda r: r['crowding_share'])
        parts.append(f"độ đông cao nhất là {100 * top['crowding_share']:.2f}% ({top['name']})")
    if adf:
        top = max(adf, key=lambda r: r['adf_p'])
        parts.append(f"p ADF lớn nhất là {top['adf_p']:.2g} ({top['name']})")
    return 'Đọc: ' + '; '.join(parts) + '.'


def _threshold_phrase(r: Dict) -> str:
    if r['threshold_ic'] is None:
        return f"{r['a']}: chưa xác định"
    return f"{r['a']}: IC {_ic(r['threshold_ic'])} (p = {_p(r['p_fisher'])})"


def primary_value_planted(detection: List[Dict]) -> str:
    """Current value of the planted chapter's primary metric: the threshold of every A."""
    if not detection:
        return MISSING
    return '; '.join(_threshold_phrase(r) for r in detection)


def reading_detection(detection: List[Dict]) -> str:
    if not detection:
        return ''
    found = [r for r in detection if r['threshold_ic'] is not None]
    head = f"Đọc: {len(found)}/{len(detection)} tín hiệu có ngưỡng phát hiện ({config_label(detection[0]['config'])}, ngân sách {num(detection[0]['budget'])}). "
    detail = '; '.join(f"{_threshold_phrase(r)}, số seed tìm lại gần {r['rates']}" if r['rates'] else _threshold_phrase(r)
                       for r in detection)
    tail = ('' if found else ' Không A nào đạt p < ' + f'{FISHER_ALPHA:g}' + ' ở mức IC nào, nên chưa xác định được ngưỡng phát hiện.')
    return head + detail + '.' + tail


def reading_near_table(rows: List[Dict]) -> str:
    """Near recovery at the highest IC of each A, with its Wilson interval."""
    if not rows:
        return ''
    last: Dict[str, Dict] = {}
    for r in rows:
        if r['a'] not in last or r['ic'] > last[r['a']]['ic']:
            last[r['a']] = r
    parts = [f"{a} ở IC {_ic(r['ic'])}: {r['near_count']}/{r['n_runs']} (Wilson {_fmt(r['low'])} đến {_fmt(r['high'])})"
             for a, r in sorted(last.items())]
    return 'Đọc: ' + '; '.join(parts) + '.'


def _significant(row: Dict) -> bool:
    return row['p_holm'] is not None and row['p_holm'] < FISHER_ALPHA


def _a_type_vi(name: str) -> str:
    return {'classical': 'A kinh điển', 'odd': 'A lạ'}.get(name, name)


def primary_value_rq1(rows: List[Dict]) -> str:
    if not rows:
        return MISSING
    return '; '.join(f"{_a_type_vi(r['a_type'])} ở {num(r['budget'])}: p Holm = {_p(r['p_holm'])}" for r in rows)


def reading_primary(rows: List[Dict]) -> str:
    """The four tests in words, how many pass after Holm, and which configuration was higher where one did."""
    if not rows:
        return ''
    cells = '; '.join(f"{_a_type_vi(r['a_type'])} ở {num(r['budget'])}: LLM + MCTS {r['near_llm_mcts']}/{r['n_llm_mcts']} so với "
                      f"MCTS không LLM {r['near_mcts_only']}/{r['n_mcts_only']}, p = {_p(r['p_two_sided'])}, "
                      f"p Holm = {_p(r['p_holm'])}" for r in rows)
    passed = [r for r in rows if _significant(r)]
    if not passed:
        verdict = (f"Không phép nào có p Holm < {FISHER_ALPHA:g}: dữ liệu không phân biệt được LLM + MCTS với MCTS không LLM "
                   'ở các ô này.')
    else:
        def direction(r):
            a = r['near_llm_mcts'] / r['n_llm_mcts']
            b = r['near_mcts_only'] / r['n_mcts_only']
            return 'cao hơn' if a > b else 'thấp hơn'
        verdict = (f"{len(passed)}/{len(rows)} phép có p Holm < {FISHER_ALPHA:g}: "
                   + '; '.join(f"{_a_type_vi(r['a_type'])} ở {num(r['budget'])}, LLM + MCTS {direction(r)}" for r in passed) + '.')
    return f"Đọc: {cells}. {verdict}"


def reading_budget(series: Dict, ic: float, mark: int) -> str:
    """Near rate of each configuration at the phase-A mark and at the last budget, per A."""
    if not series:
        return ''
    parts = []
    for a, configs in series.items():
        cells = []
        for config, points in configs.items():
            by_budget = {int(p[0]): p[1] for p in points}
            last = max(by_budget)
            at_mark = by_budget.get(mark)
            cells.append(f"{config_label(config)} {_fmt(at_mark)} → {_fmt(by_budget[last])}")
        parts.append(f"{a}: " + ', '.join(cells))
    return f"Đọc: tỷ lệ tìm lại gần ở IC {_ic(ic)}, từ mốc {num(mark)} tới mốc cuối, theo A: " + '; '.join(parts) + '.'


def reading_coverage(rows: List[Dict]) -> str:
    if not rows:
        return ''
    inside = [r for r in rows if r['in_region']]
    outside = [r['a'] for r in rows if not r['in_region']]
    parts = [f"{len(inside)}/{len(rows)} A nằm trong vùng của bộ blueprint ban đầu"]
    for r in inside:
        parts.append(f"{r['a']} qua {', '.join(f'`{b}`' for b in r['expressing'])}, blueprint nhỏ nhất có "
                     f"{num(r['completions'])} cách điền")
    if outside:
        parts.append(f"{', '.join(outside)} nằm ngoài vùng")
    return 'Đọc: ' + '; '.join(parts) + '.'


def reading_touch(rows: List[Dict]) -> str:
    """For each A at the highest IC: runs that touched it and the median iterations per configuration."""
    if not rows:
        return ''
    top = max(r['ic'] for r in rows)
    parts = []
    for a in sorted({r['a'] for r in rows}):
        cells = [f"{config_label(r['config'])} chạm {r['n_touched']}/{r['n_runs']}"
                 + (f", trung vị {num(round(r['median_iterations']))} vòng" if r['median_iterations'] is not None else '')
                 for r in rows if r['a'] == a and r['ic'] == top]
        if cells:
            parts.append(f"{a}: " + '; '.join(cells))
    return f"Đọc: ở IC {_ic(top)}, " + ' | '.join(parts) + '.'


def reading_walkforward(rows: List[Dict]) -> str:
    """Sharpe difference per configuration and whether its interval contains 0."""
    if not rows:
        return ''
    parts = []
    for r in rows:
        if r['ci_low'] is None or r['ci_high'] is None:
            parts.append(f"{config_label(r['config'])}: chênh {_fmt(r['difference'])}")
            continue
        verdict = 'khoảng chứa 0' if r['ci_low'] <= 0 <= r['ci_high'] else 'khoảng không chứa 0'
        parts.append(f"{config_label(r['config'])}: chênh {_fmt(r['difference'])} ({_fmt(r['ci_low'])} đến {_fmt(r['ci_high'])}, {verdict}, "
                     f"ρ = {_fmt(r['rho'])})")
    return 'Đọc: Sharpe(LLM + MCTS) trừ Sharpe(cấu hình), ' + '; '.join(parts) + '.'


FEEDBACK_REASONS = {
    'context_length': 'trả lời bị cắt ở giới hạn token',
    'empty_reply': 'trả lời rỗng',
    'all_rejected': 'mọi blueprint mới bị loại',
    'no_scored_formulas': 'chưa có biểu thức nào được chấm',
    'no_session_started': 'không blueprint mới nào chạy được',
    'unrecorded': 'chưa ghi lý do',
}


def reading_feedback(summary: Optional[Dict]) -> str:
    """
    One line on the feedback round of the runs a page shows, from `SearchConfigs.summarize_feedback`: runs, runs that
    fell back to the initial blueprints (with the reasons) and runs that needed a retry. Empty without feedback rounds.
    """
    if not summary or not summary.get('runs'):
        return ''
    runs, fallbacks = summary['runs'], summary['fallbacks']
    if fallbacks:
        reasons = sorted(summary['reasons'].items(), key=lambda kv: -kv[1])
        counts = ', '.join(f"{key} {n}" for key, n in reasons)
        gloss = '; '.join(f"{key} = {FEEDBACK_REASONS[key]}" for key, _ in reasons if key in FEEDBACK_REASONS)
        fell = f"{fallbacks} lượt ({fallbacks / runs:.0%}) quay về bộ blueprint ban đầu (lý do: {counts}" + (f"; {gloss}" if gloss else '') + ')'
    else:
        fell = 'không lượt nào quay về bộ blueprint ban đầu'
    return (f"Vòng phản hồi của {runs} lượt LLM + MCTS trong kết quả này: {fell}; "
            f"{summary['runs_with_retry']} lượt phải hỏi lại LLM ít nhất một lần.")


def placebo_p_text(view: Optional[Dict]) -> str:
    """p = (1 + #placebo sets with Sharpe >= real) / (K + 1); pending text while there is no real run."""
    if view is None:
        return MISSING
    return PLACEBO_P_PENDING if view['p'] is None else f"{view['p']:.3f}"


def primary_value_placebo(view: Optional[Dict]) -> str:
    if view is None:
        return MISSING
    return f"p = {placebo_p_text(view)}"


def reading_placebo(view: Optional[Dict]) -> str:
    """Placebo Sharpe distribution and what the real run must beat for the smallest p."""
    if view is None:
        return ''
    text = (f"Đọc: {view['k']} bộ placebo có Sharpe trung bình {_fmt(view['mean'])}, độ lệch chuẩn {_fmt(view['sd'])}, "
            f"nhỏ nhất {_fmt(view['min'])}, lớn nhất {_fmt(view['max'])}. Muốn p = {view['min_p']:.2f} "
            f"(nhỏ nhất có thể với {view['k']} bộ), Sharpe lần chạy thật phải lớn hơn {_fmt(view['max'])}.")
    if view['real'] is None:
        return text + ' Lần chạy thật (MCTS seed 1) chưa có nên p chưa tính được.'
    text += (f" p so các bộ placebo với Sharpe của lần chạy thật chỉ ở MCTS seed 1 (cùng seed, cùng cách đo với các bộ placebo): "
             f"{_fmt(view['real'])}, p = {view['p']:.3f}.")
    if view.get('real_mean') is not None:
        text += (f" Trung bình ngày của tất cả seed của lần chạy thật có Sharpe {_fmt(view['real_mean'])}; số này chỉ để mô tả, không có p "
                 "(lấy trung bình nhiều seed làm chuỗi mượt hơn nên không so công bằng với placebo một seed).")
    return text


def reading_near_figure(rows: List[Dict]) -> str:
    """Per A: near recovery at IC 0 and at the highest IC."""
    if not rows:
        return ''
    parts = []
    for a in sorted({r['a'] for r in rows}):
        mine = sorted((r for r in rows if r['a'] == a), key=lambda r: r['ic'])
        first, last = mine[0], mine[-1]
        parts.append(f"{a}: {first['near_count']}/{first['n_runs']} ở IC {_ic(first['ic'])} → "
                     f"{last['near_count']}/{last['n_runs']} ở IC {_ic(last['ic'])}")
    return 'Đọc: ' + '; '.join(parts) + '.'


# Thesis PDF page: the two fixed files, keyed by the `version` query value.
PDF_VERSIONS = {
    'main': {'file': 'Thesis.pdf', 'download': 'NguyenTrungAnh_Thesis.pdf', 'label': 'Bản chính'},
    'nodsr': {'file': 'Thesis_noDSR.pdf', 'download': 'NguyenTrungAnh_Thesis_noDSR.pdf', 'label': 'Bản không DSR'},
}
THESIS_PDF_TITLE = 'Luận văn (PDF)'
THESIS_PDF_INTRO = ('Bản PDF của luận văn, đọc ngay trong trình duyệt hoặc tải về. Trên điện thoại, khung nhúng thường chỉ '
                    'hiện một trang hoặc không hiện gì: dùng "Mở toàn màn hình".')
THESIS_PDF_WAITING = 'chưa có bản PDF'
THESIS_PDF_NODSR_NOTE = 'Bản không DSR là bản không có mục Deflated Sharpe Ratio (phần bổ sung tuỳ chọn).'


def format_size(size: int) -> str:
    """Size text; 1 MB = 1024 * 1024 bytes."""
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / 1024:.0f} KB" if size >= 1024 else f"{size} B"


# Guide page (/guide): texts of the timeline, checklist and department guide.
GUIDE_TITLE = 'Hướng dẫn LVTN'
GUIDE_INTRO = ('Mốc của khoa, danh sách việc đã làm và hướng dẫn của bộ môn. Ngày hôm nay tính theo giờ Việt Nam và '
               'tự cập nhật mỗi ngày, kể cả khi trang để mở.')
GUIDE_TIMELINE_TITLE = 'Dòng thời gian'
GUIDE_CHECKLIST_TITLE = 'Bảng kiểm'
GUIDE_GUIDE_TITLE = 'Hướng dẫn của khoa'
GUIDE_CHECKLIST_WAITING = 'Chưa có bảng kiểm, nên chưa vẽ được dòng thời gian và danh sách việc.'
GUIDE_GUIDE_WAITING = 'Chưa có tài liệu hướng dẫn của khoa.'
GUIDE_NO_DATES = 'Bảng kiểm chưa có dòng nào có ngày, nên chưa vẽ dòng thời gian.'
GUIDE_CDN_FAILED = 'Không nạp được bộ hiển thị markdown từ CDN; dưới đây là bản văn bản gốc.'
GUIDE_SUGGESTED_NOTE = 'Hạn "đề xuất" là hạn Claude gợi ý, chưa phải hạn của khoa.'
GUIDE_TODAY_OUTSIDE = 'Hôm nay nằm ngoài khoảng thời gian đang vẽ.'

# Sections whose deadlines are suggestions; the first section of the checklist holds the department's own.
GUIDE_SUGGESTED_SECTIONS = ('Trước khi nộp', 'Bảo vệ')
THESIS_SUBMISSION_DATE = '2027-01-20'
GUIDE_LANE_LABELS = ('Mốc khoa', 'Nghiên cứu', 'Trước khi nộp / Bảo vệ')
GUIDE_STATUS_LABELS = {'done': 'xong', 'progress': 'đang làm', 'waiting': 'chờ bạn xác nhận',
                       'blocked': 'bị chặn / rủi ro', 'todo': 'chưa'}
GUIDE_STATUS_SYMBOLS = {'done': '✅', 'progress': '🔧', 'waiting': '⏸️', 'blocked': '⛔', 'todo': '○'}
