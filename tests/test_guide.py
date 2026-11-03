import datetime

import pytest

pytest.importorskip('fastapi')
pytest.importorskip('httpx')
from fastapi.testclient import TestClient

from utilities.AppConfig import PROJECT_ROOT
from web import app as web_app
from web import guide

D = datetime.date

CHECKLIST = """# Title

intro line

## Mốc của khoa

| Việc | Nhóm | Hạn | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|---|---|
| Proposal | Mốc khoa | 2026-10-09 | ✅ | `a.pdf` |
| Duyệt   |  Mốc khoa  |   2026-10-14   |  ⏸️  |   chờ   |
| Thực hiện | Mốc khoa | 2026-10-14 → 2027-01-20 | 🔧 | |
| Nộp thesis | Mốc khoa | 2027-01-20 | chưa | |
| Nộp bản giấy | Mốc khoa | 2027-01-21 | chưa | [x](http://e.com) và [y](B.md) |
| Điều kiện | Điều kiện | — | ⏸️ | |

## Nghiên cứu

| Việc | Nhóm | Hạn | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|---|---|
| Bài cài | Nghiên cứu | 2026-10-30 | ✅ | |
| Hỏng | Nghiên cứu | 2026-13-45 | ⛔ | |
| Sai cột | Nghiên cứu | 2026-10-30 | ✅ |

## Trước khi nộp

Hạn là đề xuất.

| Việc | Nhóm | Hạn | Trạng thái | Bằng chứng / ghi chú |
|---|---|---|---|---|
| Đọc lại | Trước khi nộp | 2026-12-15 | chưa | |
"""


@pytest.fixture
def parsed():
    return guide.parse_checklist(CHECKLIST)


def rows_by_task(sections):
    return {r.task: r for s in sections for r in s.rows}


def test_parse_sections_and_statuses(parsed):
    sections, problems = parsed
    assert [s.title for s in sections] == ['Mốc của khoa', 'Nghiên cứu', 'Trước khi nộp']
    assert [s.official for s in sections] == [True, False, False]
    assert [s.suggested for s in sections] == [False, False, True]
    assert sections[2].intro == 'Hạn là đề xuất.'
    rows = rows_by_task(sections)
    assert [rows[t].status for t in ('Proposal', 'Duyệt', 'Thực hiện', 'Nộp thesis', 'Hỏng')] == [
        'done', 'waiting', 'progress', 'todo', 'blocked']
    assert len(problems) == 1 and 'Sai cột' in problems[0]
    assert 'Sai cột' not in rows


def test_parse_dates_whitespace_and_malformed(parsed):
    rows = rows_by_task(parsed[0])
    assert rows['Duyệt'].start == rows['Duyệt'].end == D(2026, 10, 14) and rows['Duyệt'].note == 'chờ'
    assert (rows['Thực hiện'].start, rows['Thực hiện'].end) == (D(2026, 10, 14), D(2027, 1, 20))
    assert rows['Điều kiện'].start is None and rows['Điều kiện'].warning == ''
    assert rows['Hỏng'].start is None and rows['Hỏng'].warning
    assert guide.parse_deadline('2026-10-14 -> 2026-10-01')[2]
    assert guide.parse_deadline('mai')[2]


def test_days_left_and_overdue(parsed):
    rows = rows_by_task(parsed[0])
    today = D(2026, 11, 3)
    assert guide.days_left(rows['Nộp thesis'], today) == 78
    assert guide.days_left(rows['Thực hiện'], today) == 78
    assert guide.days_left(rows['Điều kiện'], today) is None
    assert guide.is_overdue(rows['Duyệt'], today) and guide.countdown_text(rows['Duyệt'], today) == 'quá hạn 20 ngày'
    assert not guide.is_overdue(rows['Proposal'], today) and guide.countdown_text(rows['Proposal'], today) == ''
    assert not guide.is_overdue(rows['Nộp thesis'], today) and guide.countdown_text(rows['Nộp thesis'], today) == 'còn 78 ngày'
    assert guide.countdown_text(rows['Nộp thesis'], D(2027, 1, 20)) == 'hôm nay'
    assert not guide.is_overdue(rows['Nộp thesis'], D(2027, 1, 20))
    after = D(2027, 1, 21)
    assert guide.is_overdue(rows['Nộp thesis'], after) and guide.countdown_text(rows['Nộp thesis'], after) == 'quá hạn 1 ngày'
    assert not guide.is_overdue(rows['Thực hiện'], D(2027, 1, 20)) and guide.is_overdue(rows['Thực hiện'], after)


def test_next_official_skips_done_and_past(parsed):
    sections = parsed[0]
    assert guide.next_official(sections, D(2026, 11, 3)).task == 'Nộp thesis'
    assert guide.next_official(sections, D(2026, 10, 14)).task == 'Duyệt'
    assert guide.next_official(sections, D(2026, 10, 1)).task == 'Duyệt'  # Proposal is done, so skipped
    assert guide.next_official(sections, D(2027, 1, 21)).task == 'Nộp bản giấy'
    assert guide.next_official(sections, D(2027, 2, 1)) is None
    assert guide.submission_row(sections).task == 'Nộp thesis'


def test_timeline_geometry(parsed):
    view = guide.build_timeline(parsed[0], D(2026, 11, 3))
    assert view['today_x'] is not None and view['x0'] < view['today_x'] < view['x1']
    assert [t['label'] for t in view['ticks']][:2] == ['T11/2026', 'T12/2026']  # October 1 is before the padded start
    lanes = {i['label']: i['lane'] for i in view['items']}
    assert lanes['Proposal'] == 0 and lanes['Bài cài'] == 1 and lanes['Đọc lại'] == 2
    assert 'Hỏng' not in lanes and 'Điều kiện' not in lanes  # undated rows are not drawn
    assert next(i for i in view['items'] if i['label'] == 'Thực hiện')['kind'] == 'bar'
    assert guide.build_timeline(parsed[0], D(2030, 1, 1))['today_x'] is None
    assert guide.build_timeline([], D(2026, 11, 3)) is None


def test_note_markup():
    html = str(guide.format_note('`a<b>` [x](http://e.com) [y](B.md) <script>'))
    assert '<code>a&lt;b&gt;</code>' in html and 'href="http://e.com"' in html and 'rel="noopener' in html
    assert 'B.md' not in html.replace('>y<', '') and '<script>' not in html


def make_client(tmp_path, checklist=None, guide_text=None, today=D(2026, 11, 3)):
    if checklist is not None:
        (tmp_path / guide.CHECKLIST_FILE).write_text(checklist, encoding='utf-8')
    if guide_text is not None:
        (tmp_path / guide.GUIDE_FILE).write_text(guide_text, encoding='utf-8')
    return TestClient(web_app.create_app(str(tmp_path / 'results'), docs_dir=str(tmp_path), today=lambda: today))


def test_page_renders_with_both_files(tmp_path):
    client = make_client(tmp_path, CHECKLIST, '# Guide\n\n</script><b>x</b>')
    page = client.get('/guide')
    assert page.status_code == 200
    assert 'Còn 78 ngày tới Nộp thesis' in page.text and 'Còn 78 ngày tới hạn nộp thesis' in page.text
    assert 'quá hạn 20 ngày' in page.text and 'chờ bạn xác nhận' in page.text and 'đề xuất' in page.text
    assert 'cảnh báo khi đọc bảng kiểm' in page.text and 'ngày không hợp lệ' in page.text
    assert 'id="timeline"' in page.text and 'Hôm nay 03/11/2026' in page.text
    assert '</script><b>x</b>' not in page.text  # markdown is embedded as escaped JSON
    assert 'href="/guide"' in client.get('/').text


def test_page_overdue_after_submission(tmp_path):
    page = make_client(tmp_path, CHECKLIST, '# G', today=D(2027, 1, 21)).get('/guide')
    head = page.text[page.text.index('id="hl-next"'):page.text.index('id="hl-overdue"')]
    assert 'Đã quá hạn nộp thesis 1 ngày' in head and 'Hôm nay là hạn: Nộp bản giấy' in head


def test_page_without_files(tmp_path):
    page = make_client(tmp_path).get('/guide')
    assert page.status_code == 200
    assert 'Chưa có bảng kiểm' in page.text and 'Chưa có tài liệu hướng dẫn' in page.text


def test_page_with_checklist_only_and_garbage(tmp_path):
    assert make_client(tmp_path, CHECKLIST).get('/guide').status_code == 200
    page = make_client(tmp_path, '## A\n\n| h |\n|---|\n| x | y |\n\nnot a table | | |\n').get('/guide')
    assert page.status_code == 200 and 'Chưa có tài liệu hướng dẫn' in page.text


def test_files_are_read_on_every_request(tmp_path):
    client = make_client(tmp_path, CHECKLIST)
    assert 'Đọc lại' in client.get('/guide').text
    (tmp_path / guide.CHECKLIST_FILE).write_text(CHECKLIST.replace('Đọc lại', 'Việc mới'), encoding='utf-8')
    assert 'Việc mới' in client.get('/guide').text


def test_real_docs_parse_without_warnings():
    text = guide.read_text(web_app.default_docs_dir(), guide.CHECKLIST_FILE)
    assert text is not None and guide.read_text(web_app.default_docs_dir(), guide.GUIDE_FILE)
    sections, problems = guide.parse_checklist(text)
    assert sections and sections[0].official and guide.all_warnings(sections, problems) == []
    assert all(r.start is not None for r in sections[0].rows if r.group == 'Mốc khoa')
    assert guide.submission_row(sections) is not None


def test_default_docs_dir_is_project_docs():
    assert web_app.default_docs_dir().startswith(str(PROJECT_ROOT))
