"""
All prose of the thesis web pages: chapter list and statuses, intros, captions, plain-words
descriptions and the sentences that read a result. Templates only render what is defined here.

Sentences that quote numbers are built by functions from the computed result, never typed in.
Item fields: key, role (chính / phụ / chẩn đoán; absent when the item shows no metric), label (numbered caption prefix), title, chapter (path), rq, needs (availability
key that makes the item "done"; None = no result yet).
"""

import math
from typing import Dict, List, Optional

from strategy_workflows.PlantedSignal import NEAR_CORRELATION

STATUS_LABELS = {'done': 'Xong', 'progress': 'Đang làm', 'none': 'Chưa có kết quả'}
STATUS_MARKS = {'done': '✅', 'progress': '🔧', 'none': '–'}

NEAR_LABEL = 'tìm lại gần'
EXACT_LABEL = 'tìm lại đúng'

PLACEBO_TITLE = 'Kết quả: placebo (RQ2, kiểm soát âm)'

CHAPTERS: List[Dict] = [
    {'number': 1, 'title': 'Tổng quan', 'path': '/', 'status': 'done'},
    {'number': 2, 'title': 'Dữ liệu', 'path': '/data', 'status': 'done'},
    {'number': 3, 'title': 'Phương pháp', 'path': '/method', 'status': 'progress'},
    {'number': 4.1, 'title': 'Kết quả: bài cài tín hiệu (RQ2, kiểm soát dương)', 'path': '/results/planted',
     'needs': 'planted_runs'},
    {'number': 4.2, 'title': PLACEBO_TITLE, 'path': '/results/placebo', 'needs': 'placebo_runs'},
    {'number': 4.3, 'title': 'Kết quả: vai trò của LLM (RQ1)', 'path': '/results/rq1', 'status': 'none'},
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
    {'key': 'blueprints', 'label': 'Bảng 3.1', 'title': 'Bộ blueprint đã đóng băng', 'chapter': '/method',
     'rq': None, 'needs': 'blueprint_set'},
    {'key': 'planted_table', 'role': 'chính', 'label': 'Bảng 4.1', 'title': 'Tìm lại tín hiệu cài sẵn theo IC mục tiêu',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_runs'},
    {'key': 'planted_near', 'role': 'chính', 'label': 'Hình 4.1', 'title': 'Tỷ lệ tìm lại gần theo IC mục tiêu',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_runs'},
    {'key': 'planted_corr', 'role': 'chẩn đoán', 'label': 'Hình 4.2', 'title': 'Ứng viên gần A nhất: MCTS có chạm tới A không',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_runs'},
    {'key': 'planted_positions', 'role': 'phụ', 'label': 'Bảng 4.2', 'title': 'Tương quan vị thế tốt nhất với A',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'positions'},
    {'key': 'planted_seeds', 'role': 'phụ', 'label': 'Bảng 4.3', 'title': 'Kết quả từng seed',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_runs'},
    {'key': 'placebo_dist', 'role': 'chính', 'label': 'Hình 4.3', 'title': 'Sharpe ngoài mẫu của 19 bộ placebo so với lần chạy thật',
     'chapter': '/results/placebo', 'rq': 'RQ2', 'needs': 'placebo_runs'},
    {'key': 'rq1_table', 'role': 'chính', 'label': 'Bảng 4.4', 'title': 'Sharpe ngoài mẫu của các cấu hình so sánh',
     'chapter': '/results/rq1', 'rq': 'RQ1', 'needs': None},
    {'key': 'wf_table', 'role': 'phụ', 'label': 'Bảng 4.5', 'title': 'Sharpe ngoài mẫu theo cửa sổ walk-forward',
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

BLUEPRINT_CAPTION = ('Bộ blueprint do LLM sinh và được đóng băng cho mọi cấu hình. Gốc là toán tử ngoài cùng của '
                     'khung công thức.')

PLANTED_TITLE = 'Kết quả: bài cài tín hiệu (RQ2, kiểm soát dương)'
PLANTED_QUESTION = ('Câu hỏi: nếu trong dữ liệu có một tín hiệu biết trước, quy trình có tìm lại được nó không? '
                    'Đây là kiểm soát dương của RQ2.')
PLANTED_METHOD = [
    'Xáo thứ tự lợi suất từng nến trong mỗi đoạn dữ liệu thật để xoá mọi cấu trúc có sẵn, giữ khối lượng và hình dạng '
    'trong nến.',
    'Cài vào lợi suất kế tiếp một phần tỷ lệ với tín hiệu A, hiệu chỉnh sao cho IC (tương quan hạng của A với lợi suất '
    'nến sau) đạt một mức mục tiêu biết trước: 0, 0.05 hoặc 0.1.',
    'Chạy đúng quy trình luận văn (LLM sinh blueprint, MCTS, chọn top-5 trên đoạn kiểm định) trên dữ liệu đã cài, '
    'rồi xem top-5 có chứa A hay không.',
]
PLANTED_FORMULA_WORDS = (
    'A so sánh mức đóng cửa với đỉnh của chính nến đó: z-score cửa sổ 10 của (high − close). Vế thứ hai của công thức '
    'là z-score của (close − close), tức hằng số 0, nên không đóng góp. Tín hiệu s_t là z-score cửa sổ 10 của biểu thức '
    'này, và lợi suất nến kế tiếp được cộng thêm một phần tỷ lệ thuận với s_t.')
PLANTED_FORMULA_MISSING = 'Chưa có tệp công thức cài sẵn.'
NEAR_DEFINITION = ('Tìm lại gần: có ít nhất một công thức trong top-5 mà giá trị alpha trên đoạn tìm có tương quan '
                   'hạng tuyệt đối với A từ {threshold:.1f} trở lên. Tìm lại đúng: một công thức trong top-5 có cùng '
                   'cấu trúc, cùng trường dữ liệu và cùng hướng với A, các cửa sổ lệch không quá một bước.')
PLANTED_TABLE_RQ = 'Trả lời RQ2: quy trình có tìm lại được tín hiệu cài sẵn khi IC mục tiêu tăng dần không.'
PLANTED_NEAR_RQ = 'Trả lời RQ2: ngưỡng IC mà quy trình bắt đầu phát hiện được tín hiệu.'
PLANTED_CORR_RQ = ('Chẩn đoán cho RQ2: trong mọi ứng viên MCTS đã xếp hạng, cái gần A nhất ở từng seed giống A đến đâu '
                   '(tương quan hạng tuyệt đối). Chấm cam là ứng viên đó nằm trong top-5 được chọn (hạng kiểm định từ 1 '
                   'đến 5), chấm xanh là không; vạch ngang là ngưỡng tìm lại gần.')
PLANTED_POSITIONS_RQ = ('Trả lời RQ2: vị thế tốt nhất trong top-5 giống vị thế của A đến đâu; IC 0 cho mức tương quan '
                        'do ngẫu nhiên.')
PLANTED_SEEDS_RQ = ('Chi tiết từng lượt chạy của Bảng 4.1 (RQ2). Các cột từ "Tương quan cao nhất trong top-5" đến '
                    '"Sharpe ngoài mẫu" nói về top-5 được chọn; ba cột cuối nói về ứng viên gần A nhất trong mọi ứng '
                    'viên đã xếp hạng, có thể không nằm trong top-5 (hạng kiểm định cho biết nó đứng thứ mấy).')
MISSING = 'chưa có'
PLANTED_MISSING = 'Chưa có kết quả bài cài tín hiệu (thiếu runs.csv trong thư mục kết quả luận văn).'
ILLUSTRATION_TITLE = 'Minh hoạ: cài tín hiệu làm gì với giá'
ILLUSTRATION_LINK = 'Xem minh hoạ một bộ dữ liệu: giá thật, giá placebo, giá đã cài và tín hiệu'

PLACEBO_QUESTION = ('Câu hỏi: hệ thống có tốt hơn chính nó chạy trên dữ liệu placebo, nơi không có gì để tìm không? '
                    'Đây là kiểm soát âm của RQ2.')
PLACEBO_METHOD = ('Mỗi bộ placebo xáo thứ tự lợi suất của dữ liệu rồi chạy đúng quy trình walk-forward luận văn '
                  '(7 cửa sổ, một seed MCTS). Sharpe của bộ là Sharpe năm của chuỗi lợi suất ngày ngoài mẫu nối từ '
                  'các cửa sổ.')
PLACEBO_DIST_RQ = ('Trả lời RQ2: hệ thống tự tạo ra Sharpe ngoài mẫu cỡ nào khi không có tín hiệu. Mỗi chấm là một bộ '
                   'placebo; vạch ngang là Sharpe placebo lớn nhất.')
PLACEBO_MISSING = 'Chưa có kết quả placebo (thiếu summary.csv trong thư mục walk-forward).'
PLACEBO_P_PENDING = 'chưa có, chờ lần chạy thật'

PENDING_CHAPTERS: Dict[str, Dict] = {
    'rq1': {
        'title': 'Kết quả: vai trò của LLM (RQ1)',
        'rq': 'RQ1',
        'answers': 'LLM + MCTS có cho bộ alpha tốt hơn ngoài mẫu so với MCTS không LLM, LLM không tìm, và tìm ngẫu nhiên không.',
        'will_show': ['Bảng 4.4: Sharpe ngoài mẫu (trung bình ± độ lệch theo seed) của từng cấu hình cùng ngân sách '
                      '100.000 lần đánh giá mỗi cửa sổ.'],
        'primary': 'wf_sharpe', 'metrics': ['wf_sharpe', 'ic_rq1', 'calmar', 'turnover'],
        'condition': 'Cần mã cho các cấu hình so sánh (MCTS không LLM, LLM không tìm, tìm ngẫu nhiên): chưa viết. '
                     'Sau đó cần chạy thật sau khi đóng băng.',
    },
    'walkforward': {
        'title': 'Kết quả: chuỗi ngoài mẫu (walk-forward)',
        'rq': 'RQ1, RQ2',
        'answers': 'Chỉ số chính của luận văn: Sharpe năm của chuỗi lợi suất ngày ngoài mẫu 2022-07 → 2025-12, '
                   'dùng cho cả so sánh RQ1 và so với placebo ở RQ2.',
        'will_show': ['Bảng 4.5: Sharpe ngoài mẫu theo cửa sổ và seed.',
                      'Hình 4.4: chuỗi lợi suất ngoài mẫu nối 7 cửa sổ.'],
        'primary': 'wf_sharpe', 'metrics': ['wf_sharpe', 'window_sharpe', 'max_drawdown'],
        'condition': 'Cần đóng băng cấu hình (bộ blueprint, reward, bảng cửa sổ, ngân sách, seed) rồi chạy dữ liệu thật '
                     'đúng một lần; chưa làm.',
    },
}


PLACEBO_PRIMARY = 'placebo_p'
PLACEBO_METRICS = ['placebo_p', 'placebo_dist']
PLANTED_PRIMARY = 'near'
PLANTED_METRICS = ['target_ic', 'ic', 'near', 'fisher_p', 'exact', 'oos_sharpe_6m', 'pos_corr', 'top5_corr', 'closest_corr',
                   'val_rank']
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
    'ic': {'name': 'IC đo được',
           'measures': 'Tương quan hạng (Spearman) thực đo giữa A và lợi suất nến sau trên đoạn tìm hoặc đoạn đánh giá, '
                       'trung bình theo seed.',
           'reading': 'Gần IC mục tiêu thì việc cài tín hiệu đúng như thiết kế; chênh là nhiễu mẫu.',
           'role': 'phụ'},
    'fisher_p': {'name': 'p Fisher so với IC 0',
                 'measures': 'Xác suất thấy ít nhất chừng ấy lần tìm lại gần nếu mức IC đó không khác gì IC 0 '
                             '(kiểm định chính xác Fisher một phía, so tỷ lệ tìm lại gần với IC 0).',
                 'reading': 'Nhỏ hơn 0.05 thì coi là khác IC 0; ngưỡng phát hiện là mức IC thấp nhất đạt điều đó. '
                            'Mỗi mức chỉ có 10 seed nên kiểm định có ít sức.',
                 'role': 'phụ'},
    'near': {'name': 'Tìm lại gần',
             'measures': 'Số seed mà top-5 được chọn có ít nhất một công thức với alpha tương quan hạng tuyệt đối '
                         f'với A từ {NEAR_CORRELATION:g} trở lên.',
             'reading': 'Là tỷ lệ k/n theo IC. Tỷ lệ ở IC 0 là mức "tìm lại" do ngẫu nhiên; mức IC thấp nhất có p Fisher '
                        'nhỏ hơn 0.05 so với IC 0 là ngưỡng phát hiện.',
             'role': 'chính'},
    'exact': {'name': 'Tìm lại đúng',
              'measures': 'Số seed mà top-5 có công thức cùng cấu trúc, trường dữ liệu và hướng với A (cửa sổ lệch '
                          'tối đa một bước).',
              'reading': 'Chặt hơn tìm lại gần; thường thấp vì nhiều công thức khác cấu trúc vẫn tương quan cao với A.',
              'role': 'phụ'},
    'pos_corr': {'name': 'Tương quan vị thế với A',
                 'measures': 'Tương quan giữa vị thế giao dịch của công thức tốt nhất trong top-5 và vị thế của A.',
                 'reading': 'So với mức nhiễu ở IC 0: chỉ cao hơn hẳn mức đó mới có nghĩa là vị thế giống A.',
                 'role': 'phụ'},
    'top5_corr': {'name': 'Tương quan cao nhất trong top-5',
                  'measures': 'Tương quan hạng tuyệt đối với A của công thức giống A nhất trong 5 công thức được chọn.',
                  'reading': f'Từ {NEAR_CORRELATION:g} trở lên thì seed đó được tính là tìm lại gần.',
                  'role': 'phụ'},
    'oos_sharpe_6m': {'name': 'Sharpe ngoài mẫu 6 tháng',
                      'measures': 'Sharpe năm hoá của top-5 gộp trên 6 tháng đánh giá của bài cài tín hiệu.',
                      'reading': 'Rất nhiễu vì chỉ 6 tháng; chỉ xem xu hướng theo IC, không dùng để kết luận.',
                      'role': 'phụ'},
    'closest_corr': {'name': 'Tương quan của ứng viên gần A nhất',
                     'measures': 'Tương quan hạng tuyệt đối với A của ứng viên giống A nhất trong mọi ứng viên MCTS '
                                 'đã xếp hạng, kể cả khi nó không vào top-5.',
                     'reading': 'Đo MCTS có chạm tới A không, chưa nói bước chọn có giữ nó lại không.',
                     'role': 'chẩn đoán'},
    'val_rank': {'name': 'Hạng kiểm định',
                 'measures': 'Thứ hạng của ứng viên gần A nhất theo reward trên đoạn kiểm định.',
                 'reading': 'Từ 1 đến 5 nghĩa là nó nằm trong top-5 được chọn; lớn hơn nghĩa là bị bước chọn bỏ lỡ.',
                 'role': 'chẩn đoán'},
    'placebo_p': {'name': 'p-value placebo',
                  'measures': 'Tỷ lệ bộ placebo (dữ liệu xáo, không có gì để tìm) có Sharpe ngoài mẫu không thấp hơn '
                              'lần chạy thật.',
                  'reading': 'Càng nhỏ càng khó là may mắn; với K bộ placebo, giá trị nhỏ nhất có thể là 1/(K+1), '
                             'tức 0.05 với 19 bộ, và chỉ đạt khi Sharpe thật vượt mọi bộ placebo.',
                  'role': 'chính'},
    'placebo_dist': {'name': 'Phân bố Sharpe placebo',
                     'measures': 'Sharpe ngoài mẫu của từng bộ trong 19 bộ placebo.',
                     'reading': 'Cho thấy hệ thống tự tạo ra Sharpe cỡ nào khi không có tín hiệu; lần chạy thật phải '
                                'nằm ngoài vùng này.',
                     'role': 'phụ'},
    'wf_sharpe': {'name': 'Sharpe năm ngoài mẫu',
                  'measures': 'Sharpe hằng năm hoá của chuỗi lợi suất ngày ngoài mẫu 2022-07 → 2025-12 nối từ 7 cửa sổ.',
                  'reading': 'Chỉ số chính của luận văn; lớn hơn là tốt hơn, so giữa cấu hình hoặc với placebo.',
                  'role': 'chính'},
    'window_sharpe': {'name': 'Sharpe từng cửa sổ',
                      'measures': 'Sharpe năm hoá riêng của 6 tháng đánh giá mỗi cửa sổ.',
                      'reading': 'Cho thấy kết quả đều hay chỉ nhờ một cửa sổ; mỗi giá trị rất nhiễu.',
                      'role': 'phụ'},
    'max_drawdown': {'name': 'Sụt giảm lớn nhất',
                     'measures': 'Mức giảm lớn nhất của vốn từ đỉnh xuống đáy trong chuỗi ngoài mẫu.',
                     'reading': 'Cho biết rủi ro chịu đựng để có Sharpe đó; nhỏ hơn là tốt hơn.',
                     'role': 'phụ'},
    'ic_rq1': {'name': 'IC của bộ alpha',
               'measures': 'Tương quan hạng giữa tín hiệu của bộ alpha và lợi suất nến sau, ngoài mẫu.',
               'reading': 'Chỉ số phụ cho thấy sức dự báo, bổ sung cho Sharpe.',
               'role': 'phụ'},
    'calmar': {'name': 'Calmar',
               'measures': 'Lợi suất hằng năm chia cho sụt giảm lớn nhất.',
               'reading': 'Cao hơn là sinh lời tốt hơn so với rủi ro sụt giảm.',
               'role': 'phụ'},
    'turnover': {'name': 'Vòng quay',
                 'measures': 'Mức thay đổi vị thế trung bình, tức độ giao dịch nhiều.',
                 'reading': 'Cao nghĩa là chịu nhiều phí; giúp giải thích vì sao Sharpe chênh nhau.',
                 'role': 'phụ'},
}


def metric_rows(keys: List[str]) -> List[Dict]:
    """Glossary rows (name, what it measures, how to read, role) for a chapter's list of metrics."""
    return [dict(METRICS[k], key=k) for k in keys]


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


# --------------------------------------------------------------------------- readings of results


def _fmt(value, digits: int = 2) -> str:
    return '–' if value is None or (isinstance(value, float) and not math.isfinite(value)) else f"{value:.{digits}f}"


def _ic(value: float) -> str:
    return f"{value:g}"


def reading_table(rows: List[Dict]) -> str:
    if not rows:
        return ''
    parts = [f"IC {_ic(r['strength'])}: {r['near_count']}/{r['n_runs']}" for r in rows]
    hit = [r for r in rows if r['near_count'] > 0]
    tail = (f"seed đầu tiên tìm lại gần xuất hiện ở IC {_ic(hit[0]['strength'])}." if hit
            else 'chưa seed nào tìm lại gần.')
    return f"Đọc: tìm lại gần theo IC là {'; '.join(parts)}; {tail}"


FISHER_ALPHA = 0.05


def detection_threshold(rows: List[Dict]) -> Optional[Dict]:
    """Row of the lowest target IC > 0 whose one-sided Fisher p against IC 0 is below FISHER_ALPHA; None if none."""
    return next((r for r in rows if r['strength'] > 0 and r.get('p_fisher') is not None
                 and math.isfinite(r['p_fisher']) and r['p_fisher'] < FISHER_ALPHA), None)


def _p(value) -> str:
    return '–' if value is None or not math.isfinite(value) else f"{value:.3f}"


def threshold_text(rows: List[Dict]) -> str:
    """'Ngưỡng phát hiện: IC x (p = y)', or the sentence saying no level passes / there is no IC 0 to compare."""
    if not rows:
        return ''
    if not any(r['strength'] == 0.0 for r in rows):
        return 'Không có mức IC 0 để so nên chưa xác định được ngưỡng phát hiện'
    hit = detection_threshold(rows)
    if hit is None:
        return f"Chưa có mức IC nào có p < {FISHER_ALPHA:g}, nên chưa xác định được ngưỡng phát hiện"
    return f"Ngưỡng phát hiện: IC {_ic(hit['strength'])} (p = {_p(hit['p_fisher'])})"


def reading_near(rows: List[Dict]) -> str:
    """Rate at the highest IC, then the detection threshold decided by the one-sided Fisher test against IC 0."""
    if not rows:
        return ''
    last = rows[-1]
    interval = (f"IC {_ic(last['strength'])}: {_fmt(last['near_rate'])} "
                f"(khoảng tin cậy Wilson {_fmt(last['near_low'])} đến {_fmt(last['near_high'])})")
    tests = '; '.join(f"IC {_ic(r['strength'])}: p = {_p(r['p_fisher'])}" for r in rows if r['strength'] > 0)
    tests = f" Kiểm định Fisher một phía so với IC 0 ({tests})." if tests else ''
    return f"Đọc: {interval}.{tests} {threshold_text(rows)}."


def reading_corr(seed_rows: List[Dict], threshold: float) -> str:
    """How many seeds MCTS reached A (closest correlation >= threshold) and how many of those are in the top-5."""
    if not seed_rows:
        return ''

    def reached(r):
        v = r.get('closest_corr')
        return v is not None and v == v and float(v) >= threshold

    def in_top5(r):
        v = r.get('closest_val_rank')
        return v is not None and v == v and float(v) <= 5

    by_strength: Dict[float, List[Dict]] = {}
    for r in seed_rows:
        by_strength.setdefault(float(r['strength']), []).append(r)
    parts = []
    for strength, rs in sorted(by_strength.items()):
        hit = [r for r in rs if reached(r)]
        parts.append(f"IC {_ic(strength)}: {len(hit)}/{len(rs)} seed, {sum(in_top5(r) for r in hit)} nằm trong top-5")
    return (f"Đọc: MCTS đã chạm tới A (tương quan từ {threshold:.1f} trở lên) ở "
            f"{sum(reached(r) for r in seed_rows)}/{len(seed_rows)} seed; trong đó "
            f"{sum(reached(r) and in_top5(r) for r in seed_rows)} nằm trong top-5. Theo IC: " + '; '.join(parts) + '.')


def reading_positions(rows: List[Dict]) -> str:
    if not rows:
        return ''
    base = next((r for r in rows if r['strength'] == 0.0), None)
    others = [r for r in rows if r['strength'] != 0.0]
    parts = [f"IC {_ic(r['strength'])}: trung bình {_fmt(r['mean'])}" for r in others]
    noise = f"Mức nhiễu (IC 0) cao nhất là {_fmt(base['max'])}. " if base else ''
    return f"Đọc: {noise}{'; '.join(parts)}."


def primary_value_planted(rows: List[Dict]) -> str:
    """Current value of the planted chapter's primary metric: near recovery k/n per IC, then the detection threshold."""
    if not rows:
        return MISSING
    counts = '; '.join(f"IC {_ic(r['strength'])}: {r['near_count']}/{r['n_runs']}" for r in rows)
    return f"{counts}. {threshold_text(rows)}"


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
        return text + ' Lần chạy thật chưa có nên p chưa tính được.'
    return text + f" Sharpe lần chạy thật là {_fmt(view['real'])}, p = {view['p']:.3f}."
