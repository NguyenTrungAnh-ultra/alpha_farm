"""
Content and layout of the main-flow diagram page (/pipeline).

Editing the page = editing NODES / EDGES / GROUPS below; the template and the layout code
read them and need no change. Node fields:
    id, label, group, status (STATUSES key), x, y (top-left in SVG units), details (list of
    strings; `backticks` render as code), link (optional page path), note (optional status note).
Edge fields: from, to, label (optional), dashed (optional), arc (optional: draw over the top).
THESIS holds the header card; each research question lists the node ids it highlights on hover.
"""

import re
import textwrap
from typing import Dict, List

from markupsafe import Markup, escape

NODE_WIDTH = 200
NODE_HEIGHT = 84
LABEL_CHARS = 25
VIEW_WIDTH = 940
VIEW_HEIGHT = 650

THESIS = {
    'title': 'LLM-Guided, Dimension-Constrained Monte Carlo Tree Search for Formulaic Alpha Discovery '
             'in VN30F Index Futures',
    'title_vi': 'Tìm alpha dạng công thức cho hợp đồng tương lai chỉ số VN30F bằng MCTS có ràng buộc chiều, '
                'dẫn hướng bởi LLM',
    'question': 'Quy trình LLM + MCTS có tìm ra tín hiệu thật trên VN30F1M không, hay chỉ chọn được công thức '
                'may mắn trên chính dữ liệu đã dò? Đối tượng đánh giá là quy trình, không phải một alpha riêng lẻ.',
    'rqs': [
        {'id': 'RQ1', 'name': 'Vai trò của LLM',
         'text': 'LLM + MCTS có cho bộ alpha tốt hơn ngoài mẫu so với MCTS không LLM, LLM không tìm, '
                 'và tìm ngẫu nhiên không?',
         'nodes': ['blueprints', 'mcts', 'rq1']},
        {'id': 'RQ2', 'name': 'Bằng chứng tìm thấy',
         'text': 'Hệ thống có tốt hơn chính nó chạy trên dữ liệu placebo (không có gì để tìm), và có tìm lại được '
                 'tín hiệu cài sẵn không?',
         'nodes': ['rq2_planted', 'rq2_placebo', 'oos']},
    ],
    'method': [
        'LLM đề xuất khung công thức (blueprint) có ô `?`; MCTS điền ô trong ngữ pháp có kiểm tra chiều '
        '(giá, khối lượng, tỉ lệ, logic); backtest VN30F1M (phí, ký quỹ, khớp nến sau) cho reward.',
        'Đơn vị đánh giá: gộp top-5 trọng số đều, chỉ số chính là Sharpe năm của lợi suất ngày ngoài mẫu.',
        'Walk-forward nở dần: 7 cửa sổ, ngoài mẫu 2022-07 → 2025-12, mỗi cấu hình 5 seed.',
        'So các cấu hình cùng ngân sách 100.000 lượt chấm mỗi cửa sổ (RQ1).',
        'Kiểm soát âm: 19 bộ placebo xáo lợi suất. Kiểm soát dương: bài cài tín hiệu (RQ2).',
        'Kiểm định SPA và Deflated Sharpe; HMM chỉ mô tả rủi ro.',
        'Đóng băng mọi lựa chọn trước, chạy dữ liệu thật đúng một lần.',
    ],
}

STATUSES = {
    'done': 'Xong',
    'progress': 'Đang làm',
    'todo': 'Chưa làm',
    'reference': 'Chỉ tham khảo',
}

GROUPS = [
    {'id': 'prepare', 'label': 'Chuẩn bị', 'x': 10, 'y': 10, 'w': 920, 'h': 125},
    {'id': 'window', 'label': 'Mỗi cửa sổ walk-forward (7 cửa sổ)', 'x': 10, 'y': 140, 'w': 920, 'h': 160},
    {'id': 'result', 'label': 'Kết quả', 'x': 470, 'y': 340, 'w': 460, 'h': 115},
    {'id': 'compare', 'label': 'So sánh (trả lời câu hỏi)', 'x': 10, 'y': 490, 'w': 690, 'h': 140},
]

NODES: List[Dict] = [
    {'id': 'blueprints', 'label': '① LLM sinh blueprint', 'group': 'prepare', 'status': 'progress', 'x': 20, 'y': 40,
     'details': [
         'Model qwen3.5 4B, Ollama chạy local.',
         '20 blueprint, mỗi cái là một khung công thức có các ô `?`.',
         'Prompt mới giấu tên thị trường; các batch được chỉnh trước.',
         'Blueprint bị loại nếu chép ví dụ trong prompt, trùng khung với blueprint khác, hoặc không có `?`.',
         'Mã: `utilities/Prompts.py`, `strategy_workflows/GenerateStrategies.py`.']},
    {'id': 'freeze', 'label': 'Đóng băng', 'group': 'prepare', 'status': 'todo', 'x': 250, 'y': 40,
     'details': [
         'Trước khi chạy dữ liệu thật, đóng băng bộ blueprint (hash), reward sharpe, bảng cửa sổ, ngân sách và seed, '
         'git commit và dấu vân tay dữ liệu vào `results/walkforward/frozen.json`.',
         'Chạy dữ liệu thật đúng một lần, không đổi gì sau khi thấy kết quả.']},
    {'id': 'mcts', 'label': 'a. MCTS trên đoạn học', 'group': 'window', 'status': 'done', 'x': 20, 'y': 200,
     'note': 'mã xong, bài cài tín hiệu đang dùng',
     'details': [
         'MCTS điền các ô `?`, 5.000 vòng lặp mỗi blueprint (100.000 lần đánh giá).',
         'UCT trên reward lớn nhất. Reward sharpe = 0.6·clip(Sharpe/3) + 0.4·min(|IC|/0.15, 1), IC lấy trên z-score.',
         'Đoạn học: từ 2018-08 đến 12 tháng trước đoạn đánh giá.',
         'Mã: `strategy_workflows/MCTSEngine.py`.']},
    {'id': 'top100', 'label': 'b. 100 công thức khác nhau tốt nhất', 'group': 'window', 'status': 'done', 'x': 250, 'y': 200,
     'details': [
         'Bỏ các bản trùng của cùng một biểu thức chỉ khác tham số mẫu.',
         'Giữ tối đa 100, xếp theo reward đoạn học.']},
    {'id': 'validation', 'label': 'c. Chấm lại trên đoạn kiểm định → top-5', 'group': 'window', 'status': 'done',
     'x': 480, 'y': 200,
     'details': [
         '12 tháng ngay trước đoạn đánh giá.',
         'Chọn 5 công thức có reward kiểm định cao nhất; alpha tính trên khung dữ liệu liên tục.',
         'Mục đích: lọc các công thức chỉ tốt do may mắn trên đoạn học.']},
    {'id': 'trade', 'label': 'd. Gộp top-5, giao dịch 6 tháng đánh giá', 'group': 'window', 'status': 'done',
     'x': 710, 'y': 200, 'note': 'mã xong',
     'details': [
         'Trung bình có trọng số bằng nhau của các vị thế.',
         'Phí 6.000 VND mỗi hợp đồng mỗi chiều, ký quỹ 28,5%, ký quỹ duy trì 20%, tín hiệu ở nến t khớp ở nến t+1.',
         'Mã: `core_engine/BacktestEngine.py`.',
         'Mũi tên vòng về a là vòng lặp, không phải dữ liệu quay ngược: xong cửa sổ này thì làm lại a–d cho cửa sổ kế tiếp '
         '(thêm 6 tháng dữ liệu học). Kết quả giao dịch của d không đưa vào MCTS của cửa sổ sau.']},
    {'id': 'oos', 'label': '③ Chuỗi lợi suất ngoài mẫu 2022-07 → 2025-12 → Sharpe', 'group': 'result', 'status': 'todo',
     'x': 710, 'y': 370,
     'details': [
         'Nối 7 đoạn đánh giá thành một chuỗi lợi suất theo ngày.',
         'Báo Sharpe hằng năm hoá (chỉ số chính); IC, Calmar và vòng quay là chỉ số phụ.',
         '5 seed cho mỗi cấu hình.']},
    {'id': 'hmm', 'label': 'HMM mô tả rủi ro', 'group': 'result', 'status': 'reference', 'x': 480, 'y': 370,
     'details': ['Chỉ mô tả rủi ro của chiến lược cuối cùng (đường bootstrap), không loại gì.']},
    {'id': 'rq2_planted', 'label': 'RQ2: bài cài tín hiệu (độ nhạy)', 'group': 'compare', 'status': 'done',
     'x': 20, 'y': 520, 'note': 'lần chạy 1–3', 'link': '/planted',
     'details': [
         'Cài công thức A vào dữ liệu placebo với IC 0 / 0.02 / 0.05 / 0.1.',
         'Kết quả: khoảng 2 năm dữ liệu phát hiện được IC ≥ 0.1; khoảng 5 năm phát hiện được giữa 0.05 và 0.1.',
         'Cần làm: chạy lại với cách chia của cửa sổ 1 và bộ blueprint mới.']},
    {'id': 'rq1', 'label': 'RQ1: vai trò của LLM', 'group': 'compare', 'status': 'todo', 'x': 250, 'y': 520,
     'details': [
         'Cùng quy trình, thay ① bằng: MCTS không LLM (gốc là một `?` rỗng), LLM không tìm kiếm, và tìm ngẫu nhiên.',
         'Cùng ngân sách 100.000 lần đánh giá.']},
    {'id': 'rq2_placebo', 'label': 'RQ2: placebo (19 bộ dữ liệu xáo)', 'group': 'compare', 'status': 'todo',
     'x': 480, 'y': 520,
     'details': [
         'Lặp lại toàn bộ walk-forward trên 19 bộ dữ liệu có lợi suất bị xáo trong từng đoạn.',
         'p = tỉ lệ lần chạy có Sharpe ≥ lần chạy thật; giá trị nhỏ nhất có thể là 0.05.']},
]

EDGES: List[Dict] = [
    {'from': 'blueprints', 'to': 'freeze'},
    {'from': 'freeze', 'to': 'mcts'},
    {'from': 'mcts', 'to': 'top100'},
    {'from': 'top100', 'to': 'validation'},
    {'from': 'validation', 'to': 'trade'},
    {'from': 'trade', 'to': 'oos'},
    {'from': 'oos', 'to': 'hmm'},
    {'from': 'oos', 'to': 'rq1'},
    {'from': 'oos', 'to': 'rq2_placebo'},
    {'from': 'rq2_planted', 'to': 'mcts', 'dashed': True, 'label': 'đo độ nhạy của a–d'},
    {'from': 'trade', 'to': 'mcts', 'dashed': True, 'arc': True, 'loop': True,
     'label': '↻ lặp lại a–d cho cửa sổ kế tiếp (×7 cửa sổ, ×5 seed)'},
]


def format_text(text: str) -> Markup:
    """Escape text and turn `backticks` into <code>."""
    return Markup(re.sub(r'`([^`]+)`', r'<code>\1</code>', str(escape(text))))


def wrap_label(label: str) -> List[str]:
    return textwrap.wrap(label, LABEL_CHARS)[:3]


def _anchor(node: Dict, side: str) -> tuple:
    x, y = node['x'], node['y']
    return {'top': (x + NODE_WIDTH / 2, y), 'bottom': (x + NODE_WIDTH / 2, y + NODE_HEIGHT),
            'left': (x, y + NODE_HEIGHT / 2), 'right': (x + NODE_WIDTH, y + NODE_HEIGHT / 2)}[side]


def edge_geometry(edge: Dict, by_id: Dict[str, Dict]) -> Dict:
    """SVG path `d` and label position of one edge."""
    a, b = by_id[edge['from']], by_id[edge['to']]
    if edge.get('arc'):
        x1, y1 = _anchor(a, 'top')
        x2, y2 = _anchor(b, 'top')
        x1, x2 = x1 + 40, x2 + 40
        return {'d': f"M{x1:.0f},{y1:.0f} C{x1:.0f},{y1 - 60:.0f} {x2:.0f},{y2 - 60:.0f} {x2:.0f},{y2:.0f}",
                'lx': (x1 + x2) / 2, 'ly': y1 - 47, 'anchor': 'middle'}
    if abs(a['y'] - b['y']) < 5:
        side_a, side_b = ('right', 'left') if b['x'] > a['x'] else ('left', 'right')
        (x1, y1), (x2, y2) = _anchor(a, side_a), _anchor(b, side_b)
        return {'d': f"M{x1:.0f},{y1:.0f} L{x2:.0f},{y2:.0f}", 'lx': (x1 + x2) / 2, 'ly': y1 - 6, 'anchor': 'middle'}
    side_a, side_b = ('bottom', 'top') if b['y'] > a['y'] else ('top', 'bottom')
    (x1, y1), (x2, y2) = _anchor(a, side_a), _anchor(b, side_b)
    mid = (y1 + y2) / 2
    return {'d': f"M{x1:.0f},{y1:.0f} C{x1:.0f},{mid:.0f} {x2:.0f},{mid:.0f} {x2:.0f},{y2:.0f}",
            'lx': x2 + 6, 'ly': mid + 40 if edge.get('label') else mid, 'anchor': 'start'}


def build_view() -> Dict:
    """Template context: nodes with wrapped labels, edges with geometry, group boxes, legend."""
    by_id = {n['id']: n for n in NODES}
    nodes = [dict(n, lines=wrap_label(n['label']), status_label=STATUSES[n['status']]) for n in NODES]
    edges = [dict(e, **edge_geometry(e, by_id)) for e in EDGES]
    return {'thesis': THESIS, 'nodes': nodes, 'edges': edges, 'groups': GROUPS, 'statuses': STATUSES,
            'width': NODE_WIDTH, 'height': NODE_HEIGHT, 'view_width': VIEW_WIDTH, 'view_height': VIEW_HEIGHT}
