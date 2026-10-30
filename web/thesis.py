"""
All prose of the thesis web pages: chapter list and statuses, intros, captions, plain-words
descriptions and the sentences that read a result. Templates only render what is defined here.

Sentences that quote numbers are built by functions from the computed result, never typed in.
Item fields: key, label (numbered caption prefix), title, chapter (path), rq, needs (availability
key that makes the item "done"; None = no result yet).
"""

import math
from typing import Dict, List, Optional

STATUS_LABELS = {'done': 'Xong', 'progress': 'Đang làm', 'none': 'Chưa có kết quả'}
STATUS_MARKS = {'done': '✅', 'progress': '🔧', 'none': '–'}

NEAR_LABEL = 'tìm lại gần'
EXACT_LABEL = 'tìm lại đúng'

CHAPTERS: List[Dict] = [
    {'number': 1, 'title': 'Tổng quan', 'path': '/', 'status': 'done'},
    {'number': 2, 'title': 'Dữ liệu', 'path': '/data', 'status': 'done'},
    {'number': 3, 'title': 'Phương pháp', 'path': '/method', 'status': 'progress'},
    {'number': 4.1, 'title': 'Kết quả: bài cài tín hiệu (RQ2, kiểm soát dương)', 'path': '/results/planted',
     'needs': 'planted_runs'},
    {'number': 4.2, 'title': 'Kết quả: placebo (RQ2, kiểm soát âm)', 'path': '/results/placebo', 'status': 'none'},
    {'number': 4.3, 'title': 'Kết quả: vai trò của LLM (RQ1)', 'path': '/results/rq1', 'status': 'none'},
    {'number': 4.4, 'title': 'Kết quả: chuỗi ngoài mẫu (walk-forward)', 'path': '/results/walkforward',
     'status': 'none'},
]

ITEMS: List[Dict] = [
    {'key': 'data_bars', 'label': 'Bảng 2.1', 'title': 'Dữ liệu VN30F1M 60 phút và số nến từng đoạn walk-forward',
     'chapter': '/data', 'rq': None, 'needs': 'data'},
    {'key': 'flow', 'label': 'Hình 3.1', 'title': 'Sơ đồ luồng chính', 'chapter': '/method', 'rq': None,
     'status': 'done'},
    {'key': 'windows', 'label': 'Bảng 3.1', 'title': 'Cửa sổ walk-forward', 'chapter': '/method', 'rq': None,
     'status': 'done'},
    {'key': 'blueprints', 'label': 'Bảng 3.2', 'title': 'Bộ blueprint đã đóng băng', 'chapter': '/method',
     'rq': None, 'needs': 'blueprint_set'},
    {'key': 'planted_table', 'label': 'Bảng 4.1', 'title': 'Tìm lại tín hiệu cài sẵn theo IC mục tiêu',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_runs'},
    {'key': 'planted_near', 'label': 'Hình 4.1', 'title': 'Tỷ lệ tìm lại gần theo IC mục tiêu',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_runs'},
    {'key': 'planted_corr', 'label': 'Hình 4.2', 'title': 'Tương quan của ứng viên gần A nhất theo IC mục tiêu',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_runs'},
    {'key': 'planted_positions', 'label': 'Bảng 4.2', 'title': 'Tương quan vị thế tốt nhất với A',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'positions'},
    {'key': 'planted_seeds', 'label': 'Bảng 4.3', 'title': 'Kết quả từng seed',
     'chapter': '/results/planted', 'rq': 'RQ2', 'needs': 'planted_runs'},
    {'key': 'placebo_dist', 'label': 'Hình 4.3', 'title': 'Sharpe ngoài mẫu của 19 bộ placebo so với lần chạy thật',
     'chapter': '/results/placebo', 'rq': 'RQ2', 'needs': None},
    {'key': 'rq1_table', 'label': 'Bảng 4.4', 'title': 'Sharpe ngoài mẫu của các cấu hình so sánh',
     'chapter': '/results/rq1', 'rq': 'RQ1', 'needs': None},
    {'key': 'wf_table', 'label': 'Bảng 4.5', 'title': 'Sharpe ngoài mẫu theo cửa sổ walk-forward',
     'chapter': '/results/walkforward', 'rq': 'RQ1, RQ2', 'needs': None},
    {'key': 'wf_curve', 'label': 'Hình 4.4', 'title': 'Chuỗi lợi suất ngoài mẫu nối 7 cửa sổ',
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
PLANTED_CORR_RQ = ('Trả lời RQ2: trong mọi ứng viên đã xếp hạng, cái gần A nhất ở từng seed giống A đến đâu '
                   '(tương quan hạng tuyệt đối), kể cả khi không nằm trong top-5; vạch ngang là ngưỡng tìm lại gần.')
PLANTED_POSITIONS_RQ = ('Trả lời RQ2: vị thế tốt nhất trong top-5 giống vị thế của A đến đâu; IC 0 cho mức tương quan '
                        'do ngẫu nhiên.')
PLANTED_SEEDS_RQ = ('Chi tiết từng lượt chạy của Bảng 4.1 (RQ2). Các cột từ "Tương quan cao nhất trong top-5" đến '
                    '"Sharpe ngoài mẫu" nói về top-5 được chọn; ba cột cuối nói về ứng viên gần A nhất trong mọi ứng '
                    'viên đã xếp hạng, có thể không nằm trong top-5 (hạng kiểm định cho biết nó đứng thứ mấy).')
MISSING = 'chưa có'
PLANTED_MISSING = 'Chưa có kết quả bài cài tín hiệu (thiếu runs.csv trong thư mục kết quả luận văn).'
ILLUSTRATION_TITLE = 'Minh hoạ: cài tín hiệu làm gì với giá'
ILLUSTRATION_LINK = 'Xem minh hoạ một bộ dữ liệu: giá thật, giá placebo, giá đã cài và tín hiệu'

PENDING_CHAPTERS: Dict[str, Dict] = {
    'placebo': {
        'title': 'Kết quả: placebo (RQ2, kiểm soát âm)',
        'rq': 'RQ2',
        'answers': 'Hệ thống có tốt hơn chính nó chạy trên dữ liệu placebo, nơi không có gì để tìm không.',
        'will_show': ['Hình 4.3: phân bố Sharpe ngoài mẫu của 19 bộ placebo so với lần chạy thật, kèm p = tỷ lệ bộ '
                      'placebo có Sharpe không thấp hơn lần chạy thật.'],
        'condition': 'Chạy lại toàn bộ walk-forward trên 19 bộ dữ liệu xáo (bước placebo) sau khi đóng băng cấu hình; '
                     'chưa chạy.',
    },
    'rq1': {
        'title': 'Kết quả: vai trò của LLM (RQ1)',
        'rq': 'RQ1',
        'answers': 'LLM + MCTS có cho bộ alpha tốt hơn ngoài mẫu so với MCTS không LLM, LLM không tìm, và tìm ngẫu nhiên không.',
        'will_show': ['Bảng 4.4: Sharpe ngoài mẫu (trung bình ± độ lệch theo seed) của từng cấu hình cùng ngân sách '
                      '100.000 lần đánh giá mỗi cửa sổ.'],
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
        'condition': 'Cần đóng băng cấu hình (bộ blueprint, reward, bảng cửa sổ, ngân sách, seed) rồi chạy dữ liệu thật '
                     'đúng một lần; chưa làm.',
    },
}


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
        rows.append({'kind': 'chapter', 'label': f"Chương {chapter['number']}", 'title': chapter['title'],
                     'path': chapter['path'], 'rq': '', 'status': status, 'status_label': STATUS_LABELS[status],
                     'mark': STATUS_MARKS[status]})
        for item in ITEMS:
            if item['chapter'] == chapter['path']:
                item_state = item_status(item, availability)
                rows.append({'kind': 'item', 'label': item['label'], 'title': item['title'],
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


def reading_near(rows: List[Dict]) -> str:
    """Lowest target IC whose Wilson lower bound clears the upper bound of the IC 0 row."""
    if not rows:
        return ''
    base = next((r for r in rows if r['strength'] == 0.0), None)
    last = rows[-1]
    interval = f"IC {_ic(last['strength'])}: {_fmt(last['near_rate'])} (khoảng tin cậy {_fmt(last['near_low'])} đến {_fmt(last['near_high'])})"
    if base is None:
        return f"Đọc: {interval}; không có mức IC 0 để so."
    clear = [r for r in rows if r['strength'] > 0 and r['near_low'] > base['near_high']]
    if clear:
        threshold = f"Mức IC thấp nhất tách khỏi IC 0 theo khoảng tin cậy là {_ic(clear[0]['strength'])}."
    else:
        threshold = ('Chưa có mức IC nào có cận dưới khoảng tin cậy vượt cận trên của IC 0, '
                     'nên chưa xác định được ngưỡng phát hiện.')
    return f"Đọc: {interval}. {threshold}"


def reading_corr(seed_rows: List[Dict], threshold: float) -> str:
    if not seed_rows:
        return ''
    by_strength: Dict[float, List[float]] = {}
    for r in seed_rows:
        value = r.get('closest_corr')
        if value is not None and value == value:
            by_strength.setdefault(float(r['strength']), []).append(float(value))
    parts = [f"IC {_ic(s)}: lớn nhất {_fmt(max(v))}, {sum(x >= threshold for x in v)}/{len(v)} seed từ {threshold:.1f} trở lên"
             for s, v in sorted(by_strength.items())]
    return 'Đọc: ' + '; '.join(parts) + '.'


def reading_positions(rows: List[Dict]) -> str:
    if not rows:
        return ''
    base = next((r for r in rows if r['strength'] == 0.0), None)
    others = [r for r in rows if r['strength'] != 0.0]
    parts = [f"IC {_ic(r['strength'])}: trung bình {_fmt(r['mean'])}" for r in others]
    noise = f"Mức nhiễu (IC 0) cao nhất là {_fmt(base['max'])}. " if base else ''
    return f"Đọc: {noise}{'; '.join(parts)}."
