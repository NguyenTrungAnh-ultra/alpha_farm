"""
Content and layout of the main-flow diagram on the method page (/method).

Editing the page = editing NODES / EDGES / GROUPS below; the template and the layout code
read them and need no change. Node fields:
    id, label, group, status (STATUSES key), x, y (top-left in SVG units), details (list of
    strings; `backticks` render as code), link (optional page path), note (optional status note).
Edge fields: from, to, label (optional), dashed (optional), arc (optional: draw over the top), sides (optional pair
    of anchor sides, from / to), dx_to (optional shift of the arrival point along its side), label_at (optional
    x, y, anchor of the label).
THESIS holds the header card; each research question lists the node ids it highlights on hover.
Nodes in DERIVED_NODES take status and note from the result files (`derived_states`); the status written in NODES
is the one shown when no availability is given.
"""

import re
import textwrap
from typing import Dict, List, Optional

from markupsafe import Markup, escape

from strategy_workflows.BlueprintGeneration import MAX_GENERATED_TOKENS, MAX_REPLY_ATTEMPTS
from strategy_workflows.SearchConfigs import BudgetPlan
from web.thesis import num

NODE_WIDTH = 200
NODE_HEIGHT = 84
LABEL_CHARS = 25
VIEW_WIDTH = 940
VIEW_HEIGHT = 770
BLUEPRINT_COUNT = 20
PLAN = BudgetPlan()

THESIS = {
    'title': 'LLM-Guided, Dimension-Constrained Monte Carlo Tree Search for Formulaic Alpha Discovery '
             'in VN30F Index Futures',
    'title_vi': 'Tìm alpha dạng công thức cho hợp đồng tương lai chỉ số VN30F bằng MCTS có ràng buộc chiều, '
                'dẫn hướng bởi LLM',
    'question': 'Quy trình LLM + MCTS có tìm ra tín hiệu thật trên VN30F1M không, hay chỉ chọn được công thức '
                'may mắn trên chính dữ liệu đã dò? Đối tượng đánh giá là quy trình, không phải một alpha riêng lẻ.',
    'rqs': [
        {'id': 'RQ1', 'name': 'Vai trò của LLM',
         'text': 'Cùng giới hạn độ dài công thức, LLM đưa MCTS tới tín hiệu đúng sớm hơn hay chặn đường tới nó? '
                 'Đo trên bài cài tín hiệu (LLM + MCTS với MCTS không LLM); Sharpe walk-forward của các cấu hình '
                 'chỉ để mô tả.',
         'nodes': ['blueprints', 'mcts_a', 'feedback', 'mcts_b', 'rq2_planted', 'oos', 'rq1']},
        {'id': 'RQ2', 'name': 'Bằng chứng tìm thấy',
         'text': 'Hệ thống có tốt hơn chính nó chạy trên dữ liệu placebo (không có gì để tìm), và có tìm lại được '
                 'tín hiệu cài sẵn không?',
         'nodes': ['rq2_planted', 'rq2_placebo', 'oos']},
    ],
    'method': [
        'LLM đề xuất khung công thức (blueprint) có ô `?`; MCTS điền ô trong ngữ pháp có kiểm tra chiều '
        '(giá, khối lượng, tỉ lệ, logic); backtest VN30F1M (phí, ký quỹ, khớp nến sau) cho reward. Có một vòng phản '
        f'hồi: sau {num(PLAN.phase_a)} lượt đầu, LLM xem các biểu thức tốt nhất trên đoạn học (không kèm cửa sổ) và '
        'viết blueprint mới cho nửa ngân sách còn lại.',
        'Đơn vị đánh giá: gộp top-5 trọng số đều, chỉ số chính là Sharpe năm của lợi suất ngày ngoài mẫu.',
        'Walk-forward nở dần: 7 cửa sổ, ngoài mẫu 2022-07 → 2025-12; cấu hình có tìm kiếm chạy 5 seed, cấu hình không '
        'tìm (LLM không tìm, mua và giữ, TSMOM) một seed.',
        f'Các cấu hình tiêu cùng ngân sách {num(PLAN.total)} lượt chấm mỗi cửa sổ. RQ1: phép so chính trên bài cài tín '
        'hiệu (LLM + MCTS với MCTS không LLM, bốn kiểm định Fisher hai phía chỉnh Holm); Sharpe walk-forward của các '
        'cấu hình chỉ mô tả.',
        'Kiểm soát âm: 19 bộ placebo xáo lợi suất (RQ2). Kiểm soát dương: bài cài tín hiệu, dùng cho cả RQ1 (so '
        'sánh) và RQ2 (ngưỡng phát hiện).',
        'Kiểm định SPA và Deflated Sharpe (dự kiến); HMM chỉ mô tả rủi ro.',
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
    {'id': 'window', 'label': 'Mỗi cửa sổ walk-forward (7 cửa sổ)', 'x': 10, 'y': 140, 'w': 920, 'h': 285},
    {'id': 'result', 'label': 'Kết quả', 'x': 470, 'y': 460, 'w': 460, 'h': 115},
    {'id': 'compare', 'label': 'So sánh (trả lời câu hỏi)', 'x': 10, 'y': 610, 'w': 690, 'h': 140},
]

NODES: List[Dict] = [
    {'id': 'blueprints', 'label': '① LLM sinh blueprint', 'group': 'prepare', 'status': 'done', 'x': 20, 'y': 40,
     'note': 'bộ 20 blueprint, chờ đóng băng',
     'details': [
         'Model qwen3.5 4B với thinking bật, Ollama chạy local.',
         f'{BLUEPRINT_COUNT} blueprint, mỗi cái là một khung công thức có các ô `?`; hỏi theo lô 10 blueprint.',
         'Prompt `anon_shapes` giấu tên thị trường và ghi luật chiều; temperature 0.3, seed 2026. Prompt và tham số được '
         'chỉnh trước trên các lô thử nhỏ.',
         'Bộ cho RQ1: `results/blueprint_sets/20261031_rq1/` (0 chép ví dụ, 20 khung khác nhau, ô `?` nào cũng điền được trong độ sâu 4).',
         'Blueprint bị loại nếu chép ví dụ trong prompt, trùng khung với blueprint khác, hoặc không có `?`.',
         'Mã: `utilities/Prompts.py`, `strategy_workflows/BlueprintGeneration.py`.']},
    {'id': 'freeze', 'label': 'Đóng băng', 'group': 'prepare', 'status': 'todo', 'x': 250, 'y': 40,
     'details': [
         'Trước khi chạy dữ liệu thật, đóng băng bộ blueprint (hash), reward sharpe, bảng cửa sổ, ngân sách và seed, '
         'git commit và dấu vân tay dữ liệu vào `results/walkforward/frozen.json`.',
         'Chạy dữ liệu thật đúng một lần, không đổi gì sau khi thấy kết quả.']},
    {'id': 'mcts_a', 'label': 'a1. MCTS giai đoạn A (bộ đóng băng)', 'group': 'window', 'status': 'done', 'x': 20,
     'y': 190, 'note': 'mã xong',
     'details': [
         f'{BLUEPRINT_COUNT} blueprint đóng băng chia đều {num(PLAN.phase_a)} vòng MCTS, mỗi blueprint '
         f'{num(PLAN.phase_a // BLUEPRINT_COUNT)} vòng, trên đoạn học (từ 2018-08 đến 12 tháng trước đoạn đánh giá).',
         'MCTS điền các ô `?`; UCT trên reward lớn nhất.',
         'Reward sharpe = (0.6·clip(Sharpe/3, 0, 1) + 0.4·min(|IC|/0.15, 1)) × (1 − tương quan lớn nhất với các công '
         'thức đã tìm thấy); IC lấy trên z-score.',
         'Mã: `strategy_workflows/SearchConfigs.py` (chia ngân sách), `strategy_workflows/MCTSEngine.py`.']},
    {'id': 'feedback', 'label': 'a2. Phản hồi LLM (một vòng)', 'group': 'window', 'status': 'done', 'x': 250, 'y': 190,
     'note': 'mã xong',
     'details': [
         f'Lấy {PLAN.feedback_expressions} biểu thức khác nhau tốt nhất trên đoạn học; bỏ cửa sổ khỏi biểu thức rồi mới '
         'khử trùng, và đưa LLM không kèm cửa sổ (cùng reward, IC đoạn học; không đoạn kiểm định hay đánh giá).',
         f'LLM viết {PLAN.feedback_blueprints} blueprint mới trong một yêu cầu, thêm một yêu cầu sửa cho các ý bị loại.',
         f'Mỗi yêu cầu giới hạn {num(MAX_GENERATED_TOKENS)} token sinh ra (tính cả thinking); bị cắt hoặc rỗng thì hỏi lại '
         f'tối đa {MAX_REPLY_ATTEMPTS - 1} lần, mỗi lần seed mới.',
         'Không nhận được blueprint mới nào thì giai đoạn B dùng lại bộ ban đầu.',
         'Mã: `strategy_workflows/SearchConfigs.py`, `strategy_workflows/BlueprintGeneration.py`, `utilities/Prompts.py`.']},
    {'id': 'mcts_b', 'label': 'a3. MCTS giai đoạn B (blueprint mới)', 'group': 'window', 'status': 'done', 'x': 480,
     'y': 190, 'note': 'mã xong',
     'details': [
         f'{PLAN.feedback_blueprints} blueprint mới chia đều {num(PLAN.total - PLAN.phase_a)} vòng còn lại; tổng '
         f'{num(PLAN.total)} lần đánh giá cho cả hai giai đoạn.',
         'Bảng xếp hạng gộp ứng viên của cả hai giai đoạn.',
         'Dùng lại bộ ban đầu nếu vòng phản hồi không cho blueprint mới nào.']},
    {'id': 'top100', 'label': 'b. 100 công thức khác nhau tốt nhất', 'group': 'window', 'status': 'done', 'x': 710,
     'y': 190,
     'details': [
         'Bỏ các bản trùng của cùng một biểu thức chỉ khác tham số mẫu.',
         'Giữ tối đa 100, xếp theo reward đoạn học.']},
    {'id': 'validation', 'label': 'c. Chấm lại trên đoạn kiểm định → top-5', 'group': 'window', 'status': 'done',
     'x': 710, 'y': 320,
     'details': [
         '12 tháng ngay trước đoạn đánh giá.',
         'Chọn 5 công thức có reward kiểm định cao nhất; alpha tính trên khung dữ liệu liên tục.',
         'Mục đích: lọc các công thức chỉ tốt do may mắn trên đoạn học.']},
    {'id': 'trade', 'label': 'd. Gộp top-5, giao dịch 6 tháng đánh giá', 'group': 'window', 'status': 'done',
     'x': 480, 'y': 320, 'note': 'mã xong',
     'details': [
         'Trung bình có trọng số bằng nhau của các vị thế.',
         'Phí 6.000 VND mỗi hợp đồng mỗi chiều, ký quỹ 28,5%, ký quỹ duy trì 20%, tín hiệu ở nến t khớp ở nến t+1.',
         'Mã: `core_engine/BacktestEngine.py`.',
         'Mũi tên vòng về a1 là vòng lặp, không phải dữ liệu quay ngược: xong cửa sổ này thì làm lại a1–d cho cửa sổ kế tiếp '
         '(thêm 6 tháng dữ liệu học). Kết quả giao dịch của d không đưa vào MCTS của cửa sổ sau.']},
    {'id': 'oos', 'label': '③ Chuỗi lợi suất ngoài mẫu 2022-07 → 2025-12 → Sharpe', 'group': 'result', 'status': 'todo',
     'x': 710, 'y': 490,
     'details': [
         'Nối 7 đoạn đánh giá thành một chuỗi lợi suất theo ngày.',
         'Báo Sharpe hằng năm hoá (chỉ số chính); Sharpe từng cửa sổ và sụt giảm lớn nhất là chỉ số phụ.',
         '5 seed cho cấu hình có tìm kiếm, 1 seed cho cấu hình không tìm (LLM không tìm, mua và giữ, TSMOM).']},
    {'id': 'hmm', 'label': 'HMM mô tả rủi ro', 'group': 'result', 'status': 'reference', 'x': 480, 'y': 490,
     'details': ['Chỉ mô tả rủi ro của chiến lược cuối cùng (đường bootstrap), không loại gì.']},
    {'id': 'rq2_planted', 'label': 'Bài cài tín hiệu (RQ1, RQ2)', 'group': 'compare', 'status': 'todo',
     'x': 20, 'y': 640, 'link': '/results/planted',
     'details': [
         'Cài bốn tín hiệu A (hai kinh điển, hai lạ) vào dữ liệu xáo với IC mục tiêu 0 / 0.05 / 0.1, chia đoạn như cửa sổ 1, bộ blueprint đã đóng băng, reward `sharpe`.',
         'RQ2: ngưỡng phát hiện của LLM + MCTS theo từng A, mức IC thấp nhất có tỷ lệ tìm lại gần cao hơn IC 0 (Fisher một phía).',
         'RQ1: cùng bài đó chạy với các cấu hình khác nhau để so LLM + MCTS với MCTS không LLM.']},
    {'id': 'rq1', 'label': 'RQ1: vai trò của LLM', 'group': 'compare', 'status': 'todo', 'x': 250, 'y': 640,
     'link': '/results/rq1',
     'details': [
         'Cùng quy trình, thay ① bằng: MCTS không LLM (gốc là một `?` trần), LLM không tìm kiếm, và tìm ngẫu nhiên.',
         f'Cùng ngân sách {num(PLAN.total)} lần đánh giá; phép so chính trên bài cài tín hiệu: LLM + MCTS với MCTS không LLM, Fisher hai phía chỉnh Holm.',
         'Sharpe walk-forward của các cấu hình chỉ để mô tả (chênh Sharpe kèm khoảng tin cậy, không có p).']},
    {'id': 'rq2_placebo', 'label': 'RQ2: placebo (19 bộ dữ liệu xáo)', 'group': 'compare', 'status': 'todo',
     'x': 480, 'y': 640, 'link': '/results/placebo',
     'details': [
         'Lặp lại toàn bộ walk-forward của hệ thống LLM + MCTS có phản hồi trên 19 bộ dữ liệu có lợi suất bị xáo trong từng đoạn.',
         'p = (1 + số bộ có Sharpe ≥ lần chạy thật) / (K + 1); giá trị nhỏ nhất có thể là 0.05.']},
]

EDGES: List[Dict] = [
    {'from': 'blueprints', 'to': 'freeze'},
    {'from': 'freeze', 'to': 'mcts_a'},
    {'from': 'mcts_a', 'to': 'feedback'},
    {'from': 'feedback', 'to': 'mcts_b'},
    {'from': 'mcts_b', 'to': 'top100'},
    {'from': 'top100', 'to': 'validation'},
    {'from': 'validation', 'to': 'trade'},
    {'from': 'trade', 'to': 'oos'},
    {'from': 'oos', 'to': 'hmm'},
    {'from': 'oos', 'to': 'rq1'},
    {'from': 'oos', 'to': 'rq2_placebo'},
    {'from': 'rq2_planted', 'to': 'rq1'},
    {'from': 'rq2_planted', 'to': 'mcts_a', 'dashed': True, 'label': 'đo độ nhạy của a1–d',
     'label_at': (130, 560, 'start')},
    {'from': 'trade', 'to': 'mcts_a', 'dashed': True, 'loop': True, 'sides': ('left', 'bottom'), 'dx_to': 70,
     'label': '↻ lặp lại cho cửa sổ kế tiếp', 'label_at': (215, 395, 'start')},
]

# Nodes whose status follows the result files; see `derived_states`.
DERIVED_NODES = ('rq2_planted', 'rq1', 'rq2_placebo')


def derived_states(availability: Dict[str, bool]) -> Dict[str, Dict[str, str]]:
    """
    Status and note of the comparison nodes from the same file checks the progress table uses: the planted-signal
    benchmark (`planted_detection`), its primary tests (`rq1_primary`), the walk-forward comparison
    (`wf_comparison`) and the placebo sets (`placebo_runs`, plus `placebo_real` once the real run is in).
    """
    states = {key: {'status': 'todo', 'note': ''} for key in DERIVED_NODES}
    if availability.get('planted_detection'):
        states['rq2_planted'] = {'status': 'done', 'note': 'đã có kết quả'}
    if availability.get('rq1_primary'):
        if availability.get('wf_comparison'):
            states['rq1'] = {'status': 'done', 'note': 'so trên bài cài tín hiệu và so Sharpe walk-forward đã có'}
        else:
            states['rq1'] = {'status': 'progress',
                             'note': 'so trên bài cài tín hiệu xong; so Sharpe walk-forward chờ lần chạy thật'}
    if availability.get('placebo_runs'):
        if availability.get('placebo_real'):
            states['rq2_placebo'] = {'status': 'done', 'note': 'các bộ placebo và lần chạy thật đã có'}
        else:
            states['rq2_placebo'] = {'status': 'progress', 'note': 'các bộ placebo xong; p chờ lần chạy thật'}
    return states


def format_text(text: str) -> Markup:
    """Escape text and turn `backticks` into <code>."""
    return Markup(re.sub(r'`([^`]+)`', r'<code>\1</code>', str(escape(text))))


def wrap_label(label: str) -> List[str]:
    return textwrap.wrap(label, LABEL_CHARS)[:3]


def _anchor(node: Dict, side: str, shift: float = 0) -> tuple:
    x, y = node['x'], node['y']
    return {'top': (x + NODE_WIDTH / 2 + shift, y), 'bottom': (x + NODE_WIDTH / 2 + shift, y + NODE_HEIGHT),
            'left': (x, y + NODE_HEIGHT / 2), 'right': (x + NODE_WIDTH, y + NODE_HEIGHT / 2)}[side]


_NORMAL = {'top': (0, -1), 'bottom': (0, 1), 'left': (-1, 0), 'right': (1, 0)}


def _with_label_at(edge: Dict, geometry: Dict) -> Dict:
    if edge.get('label_at'):
        geometry['lx'], geometry['ly'], geometry['anchor'] = edge['label_at']
    return geometry


def edge_geometry(edge: Dict, by_id: Dict[str, Dict]) -> Dict:
    """SVG path `d` and label position of one edge."""
    a, b = by_id[edge['from']], by_id[edge['to']]
    if edge.get('sides'):
        side_a, side_b = edge['sides']
        (x1, y1), (x2, y2) = _anchor(a, side_a), _anchor(b, side_b, edge.get('dx_to', 0))
        (na_x, na_y), (nb_x, nb_y) = _NORMAL[side_a], _NORMAL[side_b]
        reach = 60
        d = (f"M{x1:.0f},{y1:.0f} C{x1 + na_x * reach:.0f},{y1 + na_y * reach:.0f} "
             f"{x2 + nb_x * reach:.0f},{y2 + nb_y * reach:.0f} {x2:.0f},{y2:.0f}")
        return _with_label_at(edge, {'d': d, 'lx': (x1 + x2) / 2, 'ly': (y1 + y2) / 2, 'anchor': 'middle'})
    if edge.get('arc'):
        x1, y1 = _anchor(a, 'top')
        x2, y2 = _anchor(b, 'top')
        x1, x2 = x1 + 40, x2 + 40
        return _with_label_at(edge, {
            'd': f"M{x1:.0f},{y1:.0f} C{x1:.0f},{y1 - 60:.0f} {x2:.0f},{y2 - 60:.0f} {x2:.0f},{y2:.0f}",
            'lx': (x1 + x2) / 2, 'ly': y1 - 47, 'anchor': 'middle'})
    if abs(a['y'] - b['y']) < 5:
        side_a, side_b = ('right', 'left') if b['x'] > a['x'] else ('left', 'right')
        (x1, y1), (x2, y2) = _anchor(a, side_a), _anchor(b, side_b)
        return _with_label_at(edge, {'d': f"M{x1:.0f},{y1:.0f} L{x2:.0f},{y2:.0f}", 'lx': (x1 + x2) / 2, 'ly': y1 - 6,
                                     'anchor': 'middle'})
    side_a, side_b = ('bottom', 'top') if b['y'] > a['y'] else ('top', 'bottom')
    (x1, y1), (x2, y2) = _anchor(a, side_a), _anchor(b, side_b)
    mid = (y1 + y2) / 2
    return _with_label_at(edge, {
        'd': f"M{x1:.0f},{y1:.0f} C{x1:.0f},{mid:.0f} {x2:.0f},{mid:.0f} {x2:.0f},{y2:.0f}",
        'lx': x2 + 6, 'ly': mid + 40 if edge.get('label') else mid, 'anchor': 'start'})


def build_view(availability: Optional[Dict[str, bool]] = None) -> Dict:
    """
    Template context: nodes with wrapped labels, edges with geometry, group boxes, legend. With `availability`
    (the page's result-file checks) the nodes in DERIVED_NODES take their status and note from `derived_states`.
    """
    by_id = {n['id']: n for n in NODES}
    derived = derived_states(availability) if availability is not None else {}
    nodes = []
    for n in NODES:
        n = dict(n, **derived.get(n['id'], {}))
        nodes.append(dict(n, lines=wrap_label(n['label']), status_label=STATUSES[n['status']]))
    edges = [dict(e, **edge_geometry(e, by_id)) for e in EDGES]
    return {'thesis': THESIS, 'nodes': nodes, 'edges': edges, 'groups': GROUPS, 'statuses': STATUSES,
            'width': NODE_WIDTH, 'height': NODE_HEIGHT, 'view_width': VIEW_WIDTH, 'view_height': VIEW_HEIGHT}
